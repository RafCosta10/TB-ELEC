#include <stdio.h>

enum states {BOOT, ARMED, DRILLING, FAULT, SHUTDOWN, INVALID};

int arm(int state);
int disarm(int state);
int drill(int state);
int fault(int state);
int reset_fault(int state);

int main() {
    int current_state = BOOT;

    current_state = arm(current_state);
    current_state = arm(current_state);
    current_state = arm(current_state);
    current_state = arm(current_state);
}

int arm(int state) {
    if (state != BOOT)
        return INVALID;
    
    return ARMED;
}

int drill(int state) {
    if (state != ARMED)
        return INVALID;
    
    return DRILLING;
}

int disarm(int state) {
    return ARMED;
}

int fault(int state) {
    return FAULT;
}

int reset_fault(int state) {
    return ARMED;
}