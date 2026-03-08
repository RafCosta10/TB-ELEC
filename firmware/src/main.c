#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdbool.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <conio.h>
#include <windows.h>
#else
#include <termios.h>
#include <fcntl.h>
#include <errno.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <netinet/in.h>
#endif

#define TELEMETRY_PORT 5555

// 1. DEFINITIONS
typedef enum {
    IDLE,       // System idle, waiting to be armed
    ARMED,      // Safety loop closed, ready to start
    RUNNING,    // Motor is turning, simulated mining
    FAULT,      // Error state (E-Stop, Over-temp, etc.)
    SHUTDOWN    // Safe power down
} State;

// A struct to hold our fake data
typedef struct {
    float auger_rpm;
    float target_rpm;  // Target RPM for smooth transitions
    float temperature;
    float chainage; // Distance drilled
    float voltage;
    float current;
    float load_factor; // Simulates material hardness (1.0 = normal, >1.0 = tough)
    bool e_stop_pressed;
} SystemData;

// Global state variable
State current_state = IDLE;
int loop_counter = 0; // For simulating periodic load changes

// Function Prototypes
const char* getStateName(State s);
const char* getStateToken(State s);
void print_telemetry(SystemData *data);
void update_telemetry(SystemData *data);
void print_commands(void);
bool arm(void);
bool disarm(void);
void fault(void);
bool reset_fault(SystemData *data);
bool release_estop(SystemData *data);
int kbhit_check(void);
char getch_char(void);
void handle_command(char command, SystemData *data);

#ifndef _WIN32
bool telemetry_server_init(void);
void telemetry_server_close(void);
void telemetry_try_accept_client(void);
void telemetry_poll_client_commands(SystemData *data);
void telemetry_send_json(SystemData *data);
#endif

#ifndef _WIN32
int telemetry_server_fd = -1;
int telemetry_client_fd = -1;
#endif

// ==============================================
// STATE TRANSITION FUNCTIONS
// ==============================================

// Transition to ARMED state
bool arm(void) {
    if (current_state == IDLE) {
        printf(">> System Checks Passed. ARMING...\n");
        current_state = ARMED;
        return true;
    }
    printf(">> Cannot ARM from current state: %s\n", getStateName(current_state));
    return false;
}

// Transition to IDLE state
bool disarm(void) {
    if (current_state == ARMED || current_state == RUNNING) {
        printf(">> Stopping Motor... DISARMING.\n");
        current_state = IDLE;
        return true;
    }
    printf(">> Cannot DISARM from current state: %s\n", getStateName(current_state));
    return false;
}

// Transition to FAULT state
void fault(void) {
    printf(">> E-STOP TRIGGERED! Entering FAULT state.\n");
    current_state = FAULT;
}

// Reset from FAULT state
bool reset_fault(SystemData *data) {
    if (current_state == FAULT) {
        if (data->e_stop_pressed) {
            printf(">> Cannot reset: E-Stop still pressed. Release E-Stop first.\n");
            return false;
        }
        if (data->temperature > 60.0) {
            printf(">> Cannot reset: Temperature still too high (%.1f C). Wait for cooling.\n", data->temperature);
            return false;
        }
        printf(">> Fault Cleared. Returning to IDLE.\n");
        current_state = IDLE;
        return true;
    }
    printf(">> System is not in FAULT state.\n");
    return false;
}

// Release E-Stop button
bool release_estop(SystemData *data) {
    if (data->e_stop_pressed) {
        printf(">> E-Stop Released.\n");
        data->e_stop_pressed = false;
        return true;
    }
    printf(">> E-Stop is not pressed.\n");
    return false;
}

// ==============================================
// TELEMETRY GENERATION
// ==============================================

// Update telemetry based on current state
void update_telemetry(SystemData *data) {
    loop_counter++;
    
    switch (current_state) {
        case IDLE:
            // Low current, stable voltage, cooling down
            data->auger_rpm = 0;
            data->target_rpm = 0;
            data->voltage = 24.0;
            data->current = 0.5; // Standby current
            data->load_factor = 1.0;
            // Passive cooling toward ambient (25C)
            float idle_cooling = (data->temperature - 25.0) * 0.12; // Faster cooling when idle
            data->temperature -= idle_cooling;
            if (data->temperature < 25.0) data->temperature = 25.0;
            break;

        case ARMED:
            // Similar to IDLE but ready to start
            data->auger_rpm = 0;
            data->target_rpm = 0;
            data->voltage = 24.0;
            data->current = 0.8; // Slightly higher, system ready
            data->load_factor = 1.0;
            // Slower cooling when armed (systems energized)
            float armed_cooling = (data->temperature - 25.0) * 0.10;
            data->temperature -= armed_cooling;
            if (data->temperature < 25.0) data->temperature = 25.0;
            break;

        case RUNNING:
            // Simulate hitting tough material periodically
            if (loop_counter % 50 == 0) {
                // Random load spike every ~5 seconds
                data->load_factor = 1.0 + ((float)(rand() % 60) / 100.0); // 1.0 to 1.6x
            } else {
                // Gradually return to normal
                if (data->load_factor > 1.0) {
                    data->load_factor -= 0.02;
                    if (data->load_factor < 1.0) data->load_factor = 1.0;
                }
            }
            
            // Smooth RPM transitions (ramp up/down)
            if (data->auger_rpm < data->target_rpm) {
                data->auger_rpm += 25.0; // Ramp up 25 RPM per cycle
                if (data->auger_rpm > data->target_rpm) data->auger_rpm = data->target_rpm;
            } else if (data->auger_rpm > data->target_rpm) {
                data->auger_rpm -= 30.0; // Ramp down 30 RPM per cycle
                if (data->auger_rpm < data->target_rpm) data->auger_rpm = data->target_rpm;
            }
            
            // Current proportional to RPM and load
            float base_current = (data->auger_rpm / 1500.0) * 15.0; // 15A at max RPM
            float noise = ((float)(rand() % 20) / 10.0); // 0-2A noise
            data->current = (base_current + 3.0) * data->load_factor + noise;
            
            // Voltage drop under load
            data->voltage = 24.0 - (data->current / 100.0 * 2.0); // Drop with current
            
            // Temperature dynamics: heat generation vs cooling
            // Heat generated is proportional to current (power dissipation)
            float heat_generated = data->current * 0.15; // Heating rate from current
            // Heat dissipated is proportional to temp difference from ambient (25C)
            float heat_dissipated = (data->temperature - 25.0) * 0.08; // Cooling rate
            // Net temperature change
            float temp_change = heat_generated - heat_dissipated;
            data->temperature += temp_change;
            
            // Clamp temperature to reasonable range
            if (data->temperature < 25.0) data->temperature = 25.0;
            if (data->temperature > 120.0) data->temperature = 120.0;
            
            // Movement proportional to RPM
            data->chainage += (data->auger_rpm / 1500.0) * 0.1;
            break;

        case FAULT:
            // Motor stops, current falls exponentially
            data->auger_rpm = 0;
            data->target_rpm = 0;
            data->voltage = 23.8;
            
            // Current decays exponentially toward zero
            if (data->current > 0.5) {
                data->current *= 0.85; // Exponential decay
            } else {
                data->current = 0.5; // Settles to standby
            }
            
            // Temperature stays frozen
            // Cooling only if e_stop released
            if (!data->e_stop_pressed && data->temperature > 25.0) {
                float fault_cooling = (data->temperature - 25.0) * 0.05; // Slow cooling in fault
                data->temperature -= fault_cooling;
                if (data->temperature < 25.0) data->temperature = 25.0;
            }
            break;

        case SHUTDOWN:
            // All systems off
            data->auger_rpm = 0;
            data->target_rpm = 0;
            data->voltage = 0.0;
            data->current = 0.0;
            data->load_factor = 1.0;
            break;

        default:
            break;
    }
}

// ==============================================
// HELPER FUNCTIONS
// ==============================================

// Helper to convert Enum to String for printing
const char* getStateName(State s) {
    switch(s) {
        case IDLE: return "IDLE";
        case ARMED: return "ARMED (READY)";
        case RUNNING: return "RUNNING";
        case FAULT: return "FAULT / E-STOP";
        case SHUTDOWN: return "SHUTDOWN";
        default: return "UNKNOWN";
    }
}

const char* getStateToken(State s) {
    switch(s) {
        case IDLE: return "IDLE";
        case ARMED: return "ARMED";
        case RUNNING: return "RUNNING";
        case FAULT: return "FAULT";
        case SHUTDOWN: return "SHUTDOWN";
        default: return "UNKNOWN";
    }
}

// Helper to display telemetry
void print_telemetry(SystemData *data) {
    // Move cursor to home position (0,0) without clearing - eliminates flicker
    printf("\033[H");
    
    printf("\n========================================\n");
    printf("   TBM SIMULATOR - LIVE VIEW\n");
    printf("========================================\n");
    printf("STATE:       %-20s\n", getStateName(current_state));
    printf("----------------------------------------\n");
    printf("Voltage:     %-20.2f V\n", data->voltage);
    printf("Current:     %-20.2f A\n", data->current);
    printf("Temperature: %-20.1f C\n", data->temperature);
    printf("RPM:         %.0f / %.0f (target)     \n", data->auger_rpm, data->target_rpm);
    printf("Load Factor: %.2fx %-20s\n", data->load_factor, 
           data->load_factor > 1.2 ? "[TOUGH MATERIAL!]" : "");
    printf("Chainage:    %-20.1f m\n", data->chainage);
    printf("E-Stop:      %-20s\n", data->e_stop_pressed ? "PRESSED" : "Released");
    printf("========================================\n");
}

// Helper to display available commands
void print_commands(void) {
    printf("\nAVAILABLE COMMANDS:                     \n");
    printf("  [a] Arm System     [d] Disarm System  \n");
    printf("  [s] Start Running  [e] Press E-STOP   \n");
    printf("  [u] Release E-STOP [r] Reset Fault    \n");
    printf("  [+] Increase RPM   [-] Decrease RPM   \n");
    printf("  [t] Simulate Overheat                 \n");
    printf("  [x] Shutdown & Exit                   \n");
    printf("========================================\n");
}

// Non-blocking keyboard input check
int kbhit_check(void) {
    #ifdef _WIN32
    return _kbhit();
    #else
    struct termios oldt, newt;
    int ch;
    int oldf;
    
    tcgetattr(STDIN_FILENO, &oldt);
    newt = oldt;
    newt.c_lflag &= ~(ICANON | ECHO);
    tcsetattr(STDIN_FILENO, TCSANOW, &newt);
    oldf = fcntl(STDIN_FILENO, F_GETFL, 0);
    fcntl(STDIN_FILENO, F_SETFL, oldf | O_NONBLOCK);
    
    ch = getchar();
    
    tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
    fcntl(STDIN_FILENO, F_SETFL, oldf);
    
    if(ch != EOF) {
        ungetc(ch, stdin);
        return 1;
    }
    return 0;
    #endif
}

// Get character without blocking
char getch_char(void) {
    #ifdef _WIN32
    return _getch();
    #else
    return getchar();
    #endif
}

void handle_command(char command, SystemData *data) {
    switch (command) {
        case 'a':
        case 'A':
            arm();
            break;

        case 'd':
        case 'D':
            disarm();
            break;

        case 's':
        case 'S':
            if (current_state == ARMED) {
                printf(">> Contactor Closed. DRILLING STARTED.\n");
                current_state = RUNNING;
            } else {
                printf(">> Must be ARMED before starting.\n");
            }
            break;

        case 'e':
        case 'E':
            data->e_stop_pressed = true;
            fault();
            break;

        case 'u':
        case 'U':
            release_estop(data);
            break;

        case 'r':
        case 'R':
            reset_fault(data);
            break;

        case '+':
        case '=':
            if (current_state == RUNNING) {
                data->target_rpm += 100;
                if (data->target_rpm > 2000) data->target_rpm = 2000;
                printf(">> Increasing target RPM to %.0f\n", data->target_rpm);
            } else {
                printf(">> Must be RUNNING to adjust RPM\n");
            }
            break;

        case '-':
        case '_':
            if (current_state == RUNNING) {
                data->target_rpm -= 100;
                if (data->target_rpm < 500) data->target_rpm = 500;
                printf(">> Decreasing target RPM to %.0f\n", data->target_rpm);
            } else {
                printf(">> Must be RUNNING to adjust RPM\n");
            }
            break;

        case 't':
        case 'T':
            printf(">> Simulating overheat...\n");
            data->temperature = 90.0;
            break;

        case 'x':
        case 'X':
            printf(">> Shutting down...\n");
            current_state = SHUTDOWN;
            break;

        default:
            break;
    }
}

#ifndef _WIN32
bool telemetry_server_init(void) {
    struct sockaddr_in addr;
    int opt = 1;

    telemetry_server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (telemetry_server_fd < 0) {
        perror("socket");
        return false;
    }

    if (setsockopt(telemetry_server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        perror("setsockopt");
        close(telemetry_server_fd);
        telemetry_server_fd = -1;
        return false;
    }

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(TELEMETRY_PORT);
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    if (bind(telemetry_server_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(telemetry_server_fd);
        telemetry_server_fd = -1;
        return false;
    }

    if (listen(telemetry_server_fd, 1) < 0) {
        perror("listen");
        close(telemetry_server_fd);
        telemetry_server_fd = -1;
        return false;
    }

    if (fcntl(telemetry_server_fd, F_SETFL, O_NONBLOCK) < 0) {
        perror("fcntl");
        close(telemetry_server_fd);
        telemetry_server_fd = -1;
        return false;
    }

    printf(">> Telemetry server listening on 127.0.0.1:%d\n", TELEMETRY_PORT);
    return true;
}

void telemetry_server_close(void) {
    if (telemetry_client_fd >= 0) {
        close(telemetry_client_fd);
        telemetry_client_fd = -1;
    }
    if (telemetry_server_fd >= 0) {
        close(telemetry_server_fd);
        telemetry_server_fd = -1;
    }
}

void telemetry_try_accept_client(void) {
    int client_fd;

    if (telemetry_server_fd < 0 || telemetry_client_fd >= 0) {
        return;
    }

    client_fd = accept(telemetry_server_fd, NULL, NULL);
    if (client_fd < 0) {
        return;
    }

    if (fcntl(client_fd, F_SETFL, O_NONBLOCK) < 0) {
        close(client_fd);
        return;
    }

    telemetry_client_fd = client_fd;
    printf(">> GUI connected on localhost socket.\n");
}

void telemetry_poll_client_commands(SystemData *data) {
    char buffer[64];
    ssize_t bytes_read;
    int i;

    if (telemetry_client_fd < 0) {
        return;
    }

    bytes_read = recv(telemetry_client_fd, buffer, sizeof(buffer), 0);
    if (bytes_read > 0) {
        for (i = 0; i < bytes_read; i++) {
            char c = buffer[i];
            if (c == '\n' || c == '\r') {
                continue;
            }
            handle_command(c, data);
        }
        return;
    }

    if (bytes_read == 0) {
        close(telemetry_client_fd);
        telemetry_client_fd = -1;
        printf(">> GUI disconnected.\n");
        return;
    }

    if (errno != EAGAIN && errno != EWOULDBLOCK) {
        close(telemetry_client_fd);
        telemetry_client_fd = -1;
        printf(">> GUI socket error, closing client connection.\n");
    }
}

void telemetry_send_json(SystemData *data) {
    char payload[320];
    int len;
    ssize_t sent;

    if (telemetry_client_fd < 0) {
        return;
    }

    len = snprintf(payload, sizeof(payload),
                   "{\"state\":\"%s\",\"voltage\":%.3f,\"current\":%.3f,\"temperature\":%.3f,\"auger_rpm\":%.2f,\"target_rpm\":%.2f,\"load_factor\":%.3f,\"chainage\":%.3f,\"e_stop_pressed\":%d}\n",
                   getStateToken(current_state),
                   data->voltage,
                   data->current,
                   data->temperature,
                   data->auger_rpm,
                   data->target_rpm,
                   data->load_factor,
                   data->chainage,
                   data->e_stop_pressed ? 1 : 0);

    sent = send(telemetry_client_fd, payload, (size_t)len, 0);
    if (sent < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
        close(telemetry_client_fd);
        telemetry_client_fd = -1;
        printf(">> Failed to send telemetry, client disconnected.\n");
    }
}
#endif

// ==============================================
// 2. MAIN LOOP (The "Brain")
// ==============================================
int main() {
    SystemData sensors = {0.0, 1500.0, 25.0, 0.0, 24.0, 0.5, 1.0, false}; // Initial values
    char command = 0;

    printf("--- TBM BRAIN SIMULATOR INITIALIZED ---\n");
    printf("Starting live display in 2 seconds...\n");
    #ifdef _WIN32
    Sleep(2000);
    #else
    sleep(2);
    #endif

    #ifndef _WIN32
    if (!telemetry_server_init()) {
        printf(">> Warning: telemetry socket unavailable, continuing without GUI stream.\n");
    }
    #endif
    
    // Clear screen once at startup
    #ifdef _WIN32
    system("cls");
    #else
    printf("\033[2J\033[H");
    #endif

    // The Infinite Loop (Simulating the Teensy)
    while (current_state != SHUTDOWN) {

        #ifndef _WIN32
        telemetry_try_accept_client();
        telemetry_poll_client_commands(&sensors);
        #endif
        
        // A. UPDATE TELEMETRY BASED ON STATE
        update_telemetry(&sensors);

        // B. CHECK SAFETY INTERLOCKS (Automatic Transitions)
        if (sensors.temperature > 80.0 && current_state != FAULT) {
            sensors.e_stop_pressed = true;
            fault();
        }

        // C. DISPLAY TELEMETRY AND COMMANDS
        print_telemetry(&sensors);
        print_commands();

        #ifndef _WIN32
        telemetry_send_json(&sensors);
        #endif

        // D. CHECK FOR USER INPUT (Non-blocking)
        if (kbhit_check()) {
            command = getch_char();

            // E. STATE MACHINE LOGIC (Using transition functions)
            handle_command(command, &sensors);
        }
        
        // F. Update rate (10 Hz = 100ms)
        #ifdef _WIN32
        Sleep(100);
        #else
        struct timespec ts = {0, 100000000};
        nanosleep(&ts, NULL);
        #endif
    }

    #ifndef _WIN32
    telemetry_server_close();
    #endif

    printf("\n--- SYSTEM SHUTDOWN COMPLETE ---\n");
    return 0;
}