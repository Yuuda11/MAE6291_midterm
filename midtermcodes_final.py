import RPi.GPIO as GPIO
import time
import numpy as np
import smbus2 as smbus

TRIG = 16    
ECHO = 18    
RedLED = 33   
GreenLED = 35 
BUZZER_PIN = 11  
BUTTON = 13 

BUS = smbus.SMBus(1)
LCD_ADDR = None
BLEN = None

def write_word(data):
    global BLEN
    temp = data
    if BLEN == 1:
        temp |= 0x08
    else:
        temp &= 0xF7
    BUS.write_byte(LCD_ADDR, temp)

def send_command(comm):
    buf = comm & 0xF0
    buf |= 0x04  
    write_word(buf)
    time.sleep(0.002)
    buf &= 0xFB  
    write_word(buf)
    
    buf = (comm & 0x0F) << 4
    buf |= 0x04
    write_word(buf)
    time.sleep(0.002)
    buf &= 0xFB
    write_word(buf)

def send_data(data):
    buf = data & 0xF0
    buf |= 0x05  
    write_word(buf)
    time.sleep(0.002)
    buf &= 0xFB
    write_word(buf)
    
    buf = (data & 0x0F) << 4
    buf |= 0x05
    write_word(buf)
    time.sleep(0.002)
    buf &= 0xFB
    write_word(buf)

def lcd_init(addr, bl):
    global LCD_ADDR, BLEN
    LCD_ADDR = addr
    BLEN = bl
    try:
        send_command(0x33)
        time.sleep(0.005)
        send_command(0x32)
        time.sleep(0.005)
        send_command(0x28)
        time.sleep(0.005)
        send_command(0x0C)
        time.sleep(0.005)
        send_command(0x01)
        BUS.write_byte(LCD_ADDR, 0x08)
    except Exception as e:
        print("LCD initialization error:", e)
        return False
    return True

def lcd_clear():
    send_command(0x01)

def lcd_write(x, y, text):
    if x < 0:
        x = 0
    if x > 15:
        x = 15
    if y < 0:
        y = 0
    if y > 1:
        y = 1
    addr = 0x80 + 0x40 * y + x
    send_command(addr)
    for ch in text:
        send_data(ord(ch))

def display_status(line1, line2):
    lcd_clear()
    lcd_write(0, 0, line1)
    lcd_write(0, 1, line2)

measurement_time = 2      
measurement_interval = 0.1 
cycle_wait_time = 10       

TRASHCAN_HEIGHT = 32

def distance():
    GPIO.output(TRIG, False)
    time.sleep(0.000002)
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)
    
    while GPIO.input(ECHO) == 0:
        start_time = time.time()
    while GPIO.input(ECHO) == 1:
        end_time = time.time()
    
    duration = end_time - start_time
    distance_cm = duration * 34000 / 2
    return distance_cm

def measure_cycle():
    distances = []
    start_cycle = time.time()
    while (time.time() - start_cycle) < measurement_time:
        d = distance()
        distances.append(d)
        time.sleep(measurement_interval)
    if distances:
        avg_distance = sum(distances) / len(distances)
    else:
        avg_distance = TRASHCAN_HEIGHT  
    return avg_distance

Buzz = None  

def alarm():
    GPIO.output(RedLED, GPIO.HIGH)
    GPIO.output(GreenLED, GPIO.LOW)
    global Buzz
    Buzz.start(50)  
    
    lcd_clear()
    lcd_write(0, 0, "Trash FULL!")
    lcd_write(0, 1, "Press button")
    print("Trash full! Alarm activated. Waiting for button press...")
    
    while GPIO.input(BUTTON) == GPIO.HIGH:
        time.sleep(0.1)
    
    Buzz.stop()
    GPIO.output(RedLED, GPIO.LOW)
    GPIO.output(GreenLED, GPIO.HIGH)
    lcd_clear()
    lcd_write(0, 0, "Alarm off")
    lcd_write(0, 1, "Trash OK")
    print("Alarm cleared via button press.")
    time.sleep(2)

def setup():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(TRIG, GPIO.OUT)
    GPIO.setup(ECHO, GPIO.IN)
    GPIO.setup(RedLED, GPIO.OUT)
    GPIO.setup(GreenLED, GPIO.OUT)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.setup(BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    global Buzz
    Buzz = GPIO.PWM(BUZZER_PIN, 440)
    
    if not lcd_init(0x27, 1):
        print("Failed to initialize LCD.")

def destroy():
    GPIO.cleanup()
    BUS.close()

def main():
    setup()
    try:
        while True:
            avg_distance = measure_cycle()
            print("Average distance:", avg_distance, "cm")
            
            if avg_distance > TRASHCAN_HEIGHT:
                avg_distance = TRASHCAN_HEIGHT
            
            if avg_distance < 10:
                percent_full = 100
            else:
                percent_full = int(round(((TRASHCAN_HEIGHT - avg_distance) / TRASHCAN_HEIGHT) * 100))
                if percent_full > 100:
                    percent_full = 100
                if percent_full < 0:
                    percent_full = 0
            
            status_text = "{}% Full".format(percent_full)
            print("Trash status:", status_text)
            
            for sec in range(cycle_wait_time, 0, -1):
                display_status(status_text, "Next: {} sec".format(sec))
                time.sleep(1)
            
            if percent_full >= 100:
                alarm()
    except KeyboardInterrupt:
        print("Program interrupted by user.")
    finally:
        destroy()

if __name__ == '__main__':
    main()
