#include <stdio.h>

enum states {BOOT, ARMED, DRILLING, FAULT, SHUTDOWN};

int arm(int state);
int disarm(int state);
int fault(int state);
int reset_fault(int state);

int main() {
    enum current_state = BOOT;


}

int arm(int state) {
    
}