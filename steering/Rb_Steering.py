
# This code is usefull for the Rb after calibration of its frequency offset. 
 

import serial
from datetime import datetime, timedelta
from datetime import timezone
import time
import csv
import os
import struct
import threading
import serial.tools.list_ports
import numpy as np
from serial import serialutil

import pandas as pd
import asyncio
import math
import socketio
import json
from flask import Flask
from flask_socketio import SocketIO




set_point =0
read_count =0
tuning_constant = 2.28 * (10 ** -7) 
signal = threading.Event()
first_phase_corr1 = True
first_phase_corr2 = True
phase_time_const = 20
TIC_count1 =0 # Count the readings whern TIC > 1 us
TIC_count2 =0 # Count the readings when 100 ns <TIC < 1 us
# TIC_count3 =0 # Count the readings whrn 20ns <TIC < 100 ns
# TIC_count4 =0 # Count the readings whrn 20ns <TIC < 100 ns
curr_Rb_float = 0.00




# Initialize serial port
Rb_ser = None
try:
    Rb_ser = serial.Serial(port='COM16', baudrate=9600, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, timeout=1)
    print("Rb port is open now:", Rb_ser.is_open)
except serial.serialutil.SerialException as e:
    print(f"Could not open the port: {e}")
    if Rb_ser and Rb_ser.is_open:
        Rb_ser.close()

# def send_command(command):
#     try:
#         Rb_ser.write(command.encode())
#         time.sleep(1)
#         Rb_response = Rb_ser.readline().decode().strip()
#         return Rb_response
#     except Exception as e:
#         print(f"Error sending command: {e}")
#         return None

def hex_to_signed_24bit_decimal(hex_value):
    try:
        binary_value = format(int(hex_value, 16), '024b')
        return int(binary_value, 2) if binary_value[0] == '0' else -((1 << 24) - int(binary_value, 2))
    except ValueError:
        print("Invalid hexadecimal input.")
        return None

def decimal_to_24bit_hexadecimal(decimal_value):
    if decimal_value >= 0:
        binary_value = format(decimal_value, '024b')
    else:
        binary_value = format((1 << 24) + decimal_value, '024b')
    return f'0x{format(int(binary_value, 2), "06X")}'

# def freq_adjustment(current_value_dec, correction_hz):
#     current_rb_hz = tuning_constant * current_value_dec
#     Total_corr_hz = current_rb_hz + correction_hz
#     correction_dec = round(Total_corr_hz / tuning_constant)
#     correction_hex = decimal_to_24bit_hexadecimal(correction_dec)
#     return correction_dec, correction_hex



def read_current_Rb():   
    
    Read_cmd = "PD?"
    print("Reading the current shift from Rb PD?")

    full_command = Read_cmd + '\r\n'

    try:
        # Rb_ser.write(bytes.fromhex(Read_cmd))
        Rb_ser.write(full_command.encode('ascii'))
        print(f"Sent command: {full_command.strip()}")
    except serial.serialutil.PortNotOpenError as e:
        print(f"Port not open error: {e}")
        try:
            Rb_ser.open()
            Rb_ser.write(full_command.encode('ascii'))
        except serial.serialutil.SerialException as n:
            print(f"Port could not open error: {n}")
            return (None)
    
    except serial.serialutil.SerialException as e:
        print(f"Serial error: {e}")
        return (None)  # Additional catch for general serial errors

            # Rb_ser.close()
            # Rb_ser.open()
            # Rb_ser.write(bytes.fromhex(Read_RAM))
    # time.sleep(0.5)  # Wait for the device to process the write command

    data_read = Rb_ser.readline()
    # print(f"Response for PD? : {data_read}]")

    # Check if the received data is of the expected length
    if data_read == "!":
        print(f"Warning: Received {len(data_read)} ")
        return (None)

    # data_read = Rb_ser.read(9)
    #  # Check if the received data is of the expected length
    # if len(data_read) != 9:
    #     print(f"Warning: Received {len(data_read)} bytes, expected 9.")
    #     return (None)
       
    
    # Flush any stale data from the serial buffer
    Rb_ser.flushInput()
    
    return data_read




def current_freq_status():
    """Send a command to the Rubidium clock and return the response."""
    try:
        if not Rb_ser.is_open:
            Rb_ser.open()

        # full_command = 'OT?' + '\r\n'
        full_command = 'OT?'
        # Rb_ser.write(full_command.encode('ascii'))
        Rb_ser.write(full_command.encode())
        # Rb_ser.write(full_command)
        print(f"Sent command: {full_command.strip()}")

        # Wait for the device to respond
        time.sleep(0.5)

        # Read the response
        # response = Rb_ser.readline().decode('ascii').strip()
        response = Rb_ser.readline().decode().strip()
        # response = Rb_ser.readline().strip(3)
        print(f"Received response: {response}")
        parts = response.split()
        
        if len(parts) >= 3:
            decimal_value = hex_to_signed_24bit_decimal(parts[0])
            return decimal_value  # Return the decimal value of the current frequency offset
        
            # for i in range(1):
            #     print(f"\nIteration {i + 1}:")
            #     correction_dec, correction_hex = apply_correction(decimal_value,-0.001)
            #     print("Correction in Decimal:", correction_dec)
            #     print("Correction in Hexadecimal:", correction_hex)

            #     ott_command = f"OTT{correction_hex[2:]}"
            #     print("Sending command:", ott_command)
            #     send_command(ott_command)

            #     decimal_value = correction_dec
            #     time.sleep(0.5)
        else:
            return None
      
    except Exception as e:
        print(f"Error sending command to Rb Current status : {e}")
        return None
    finally:
        if Rb_ser.is_open:
            Rb_ser.flush()
            Rb_ser.close()



# def Phase_adjustment(correction_value):
    
    
#     response = send_command("PD?")

#     # Read the current 1PPS offset value from the Rb
#     Current_Rb_value = 



# Following function is to apply corrections to Rb. (Value , Flag) corr_Value = TIC value (s) or slope, Flag =0 means phase correction and Flag =1 is Frequency correction 
def apply_Phase_correction(corr_value, Flag):
    cmd_send = True
    Max_Pos_phase_limit = 0.480 # 500 milli seconds
    Max_Neg_phase_limit = 0.480 # -480 milli seconds 

    print(f"Corrected Value: {corr_value}")

    try:
        if not Rb_ser.is_open:
            Rb_ser.close()
            time.sleep(1)
    except:
        temp =4 

    """Apply the correction to the Rubidium clock."""
    
    if Flag == 0:  #  Apply zero offset tcorrection to the Rb. This makes the Rb offset wrt Reference to be zero. 
        
        Rb_not_respond = True

        while Rb_not_respond: # Loop to read Rb value till a valid response

            curr_Rb_value = read_current_Rb().decode('utf-8').strip()
            current_Rb_value = curr_Rb_value.split()[0]  # Get the first part (the number)
            
            if current_Rb_value != '!' :
                Rb_not_respond = False
                print(f"Rb Response : {current_Rb_value}")
            
            else: 
                print("Waiting for Rb response")

            time.sleep(0.8)

        print(f"Current Rb value for Phase Adjustment: {current_Rb_value}")

        # if current_Rb_value != None:
            # curr_Rb_float = current_Rb_value
            
            # # print(type(curr_Rb_float))
            # Curr_Rb_offset = float(curr_Rb_float)* 1E-9 # Convert the read value from nano seconds to seconds 

            # if Curr_Rb_offset != None:
                
            #     Total_corr = 0
            
        Total_corr = 0.00000000
        # Apply the correction to the Rubidium clock
        command = f"PD {Total_corr:.8f}"
        
        try:
            if not Rb_ser.is_open:
                Rb_ser.open()

            # Rb_ser.write("PD 0.00".encode('ascii'))
            full_command = command + '\r\n'
            #Rb_ser.write(full_command.encode('ascii'))
            print(f"Rb current value: {current_Rb_value}")
            # print(f"Rb current value: {type(current_Rb_value)}")
            
            while current_Rb_value != '000000000': # Reapet the loop untill the response of the Rb is zero as we are trying to apply 0 
                
                # Rb_ser.write("PD 0.000000000")
                Rb_ser.write(full_command.encode('ascii'))
                # print(f"Rb port open status: {Rb_ser}")
                print(f"Command send in first call: {command}")
                print(f"current Rb value after first adjustment to zero : {current_Rb_value}")
                Rb_ser.flush()

                while cmd_send: # Loop to read Rb value till a valid response
                    
                    curr_Rb_value = read_current_Rb().decode('utf-8').strip()
                    current_Rb_value = curr_Rb_value.split()[0]  # Get the first part (the number)
                    print(f"Current Rb value : {current_Rb_value}")
                    # print(f"Current Rb value : {type(current_Rb_value)}")
                    # if current_Rb_value != '!' and command != current_Rb_value:
                    if current_Rb_value != '!' :
                        cmd_send = False
                        print(f"Rb response after correction: {current_Rb_value}")
                    time.sleep(1)

                Rb_ser.close()
                
                time.sleep(5)
                Rb_ser.open()

        
        except Exception as e:
            print(f"Error sending command to RB '{command}': {e}")
            return None
                    

    if Flag == 1 : # Read the current offset wrt reference in your TIC and apply exactly opposite value 
        Rb_not_respond = True

        while Rb_not_respond: # Loop to read Rb value till a valid response

            curr_Rb_value = read_current_Rb().decode('utf-8').strip()
            current_Rb_value = curr_Rb_value.split()[0]  # Get the first part (the HEX number)
            
            if current_Rb_value != '!' :
                Rb_not_respond = False
                print(f"Rb Response : {current_Rb_value}")
            
            else: 
                print("Waiting for Rb response")

            time.sleep(0.8)

        print(f"Current Rb value: {current_Rb_value}")

        if current_Rb_value != None:
            # curr_Rb_float = current_Rb_value
            
            # Convert the hexadecimal string to a decimal integer
            # curr_Rb_int = int(current_Rb_value, 16)
            curr_Rb_int= hex_to_signed_24bit_decimal(current_Rb_value)
            # print(type(curr_Rb_float))
            

            if curr_Rb_int != None:
                
                Curr_Rb_offset = float(curr_Rb_int)* 1E-9 # Convert the read value from nano seconds to seconds 

                print(f"Rb offset convered from current Rb float value: {Curr_Rb_offset}")
                
                # Apply correction as in the first call the Rb is set to zero 
                print(f"corrected value from the TIC for the corrections: {corr_value*1E+9}")
                
                # Check if the TIC value/current output  of Rb is more than 500 ms 
                if abs(corr_value) >= Max_Pos_phase_limit:

                    if corr_value > 0:
                        Total_corr = -Max_Neg_phase_limit

                    elif corr_value < 0:
                        Total_corr = Max_Pos_phase_limit
                
                elif abs(corr_value) < Max_Pos_phase_limit:
                    
                    Total_corr = -(corr_value + 10E-9)

                                
                # Apply the correction to the Rubidium clock
                command = f"PD {Total_corr:.9f}"
                
                try:
                    if not Rb_ser.is_open:
                        Rb_ser.open()

                    # full_command = command + '\r\n'
                    #Rb_ser.write(full_command.encode('ascii'))

                    Rb_ser.write(command.encode('ascii'))
                    
                    while cmd_send: # Loop to read Rb value till a valid response
                        
                        curr_Rb_value = read_current_Rb().decode('utf-8').strip()
                        current_Rb_value = curr_Rb_value.split()[0]  # Get the first part (the number)
                        
                        # if current_Rb_value != '!' and command != current_Rb_value:
                            # cmd_send = False
                        
                        if current_Rb_value != '!':
                            cmd_send = False
                        
                        time.sleep(0.8)

                    # Rb_ser.write(command)
                    print(f"Sent command: {command.strip()}")
                    # time.sleep(0.1)

                    # Flush any stale data from the serial buffer
                    Rb_ser.flushInput()
                    
                except Exception as e:
                    print(f"Error sending command to RB '{command}': {e}")
                    return None
                    
                    
            else: # Error in reading the current Rb value 
                return None
                
                
                
                
                
                # Total_corr = (corr_value ) - 100E-9
                                
                # if abs(Total_corr) < 100E-9:
                #      Total_corr = Total_corr + 50E-9

                # if abs(Total_corr) = 
                # Calculate correction values
                # correction_applied = average_tic_ns
                # total_correction = current_offset + correction_applied
                
                # # Check that the total correction that can be applied is within the allowed limits {-500 ms to +499 ms}
                # if abs(Total_corr) >= 0.500000000:
                #     if Total_corr < 0: 
                #         corr_to_be = -0.450000000
                #     else:
                #         corr_to_be = 0.450000000

                # else:
                #     corr_to_be = Total_corr
                
                # Check that the correction to be applied is within the allowed limits {-500 ms to +499 ms} from the current offset value. 

                # threshold_value = corr_to_be + Curr_Rb_offset 

                # print(f"Threshold value: f{threshold_value}")
                # if abs(threshold_value) == 0:
                #     apply_corr = -(corr_to_be - (Curr_Rb_offset* 1E-9) - 20E-9) 

                # elif abs(threshold_value) > 0.500000000 :
                #     # Calculate applied correction based on the threshold
                #     apply_corr = - (corr_to_be - (Curr_Rb_offset* 1E-9) )
                # else:
                #     apply_corr = corr_to_be

                # Apply the correction to the Rubidium clock
                # command = f"PD {corr_to_be:.9f}"
            
            # try:
            #     if not Rb_ser.is_open:
            #         Rb_ser.open()

            #     full_command = command + '\r\n'
            #     #Rb_ser.write(full_command.encode('ascii'))

            #     #Rb_ser.write(command.encode('ascii'))
                
            #     while cmd_send: # Loop to read Rb value till a valid response
                    
            #         curr_Rb_value = read_current_Rb().decode('utf-8').strip()
            #         current_Rb_value = curr_Rb_value.split()[0]  # Get the first part (the number)
                    
            #         if current_Rb_value != '!' and command != current_Rb_value:
            #             cmd_send = False
                    
            #         time.sleep(0.8)

                
            #     # Rb_ser.write(command)
            #     print(f"Sent command: {full_command.strip()}")
            #     # time.sleep(0.1)

            #     # Flush any stale data from the serial buffer
            #     Rb_ser.flushInput()
                
            # except Exception as e:
            #     print(f"Error sending command to RB '{command}': {e}")
            #     return None
        
        # else: # Error in reading the current Rb value 
        #     return None
 

def send_freq_cmd(freq_input):
    
    correction_dec = round(freq_input / tuning_constant)
    correction_hex = decimal_to_24bit_hexadecimal(correction_dec)

    # return correction_dec, correction_hex
    command = f"OTT{correction_hex[2:]}"
    print("Sending OTT command:", command)
    
    try:
        if not Rb_ser.is_open:
            Rb_ser.open()

        full_command = command + '\r\n'
        Rb_ser.write(full_command.encode('ascii'))
        # while current_Rb_value != '000000000': # Reapet the loop untill the response of the Rb is zero as we are trying to apply 0 
        # print(f"Rb port open status: {Rb_ser}")
        print(f"Frequency adjustment command: {full_command}")
        Rb_ser.flush()
        
    except Exception as e:
        print(f"Error sending command to RB '{command}': {e}")
        return None
            
          


def apply_Freq_correction(apply_Rb_Hz, Freq_steer ):
    
    # Max_freq_limit = 1.0755 # In Hz
    Max_freq_limit = 1.0757 # In Hz
    Min_freq_limit = 1.075535964 # In Hz
    # Frequency_adjustment(slope, correction_value)
    # print("Frequency adjustments to be handeled")

    # def freq_adjustment(current_value_dec, correction_hz):
    
    Rb_curr_decimal = current_freq_status() 

    if Rb_curr_decimal is not None:
        # print("Response from Rubidium clock:", response)
        current_rb_hz = tuning_constant * Rb_curr_decimal
        print(f"current Rb value in Hz: {current_rb_hz}")

        
        # if Freq_steer:

        Req_corre = apply_Rb_Hz
            
        # else:
        #     Req_corre = 0.001* current_rb_hz # Required correction to compensate the slope 

        
        corr_limt_hz = (Req_corre + current_rb_hz) # corre_limt_hz is to cross check the anticipated position of the frequency offset after applying the corrections 

        print(f" Current applied/required Rb Correction : {corr_limt_hz}")

        # The following conditions check the status of the frequency offset to be with in limits after applying the corretions 
        
        # if abs(corr_limt_hz) <=  Max_freq_limit and abs(corr_limt_hz) > Min_freq_limit :
        if abs(corr_limt_hz) <=  Max_freq_limit :
            send_freq_cmd(Req_corre) #in Hz
            # send_freq_cmd(corr_limt_hz) #in Hz


        elif abs(corr_limt_hz) >  Max_freq_limit:
            
            corr_outof_limit = True # Correction applied is not in limits 
            fraction_part= 2 # Fraction part of the applied correction 
            initial_req_corre = Req_corre  # Store the initial Req_corre value


            if corr_limt_hz > 0:
                corr_limt_hz = Max_freq_limit
            else:
                corr_limt_hz = -Max_freq_limit



            # while corr_outof_limit:
                
            #     # Req_corre = (0.001* current_rb_hz)/fraction_part  # Required correction to compensate the slope 
                
            #     Req_corre = initial_req_corre/fraction_part
                
                
            #     corr_limt_hz = Req_corre + current_rb_hz # corre_limt_hz is to cross check the anticipated position of the frequency offset after applying the corrections 

            #     print(f"Frequency correction out of limits : {corr_limt_hz: .8f} and fraction part: {fraction_part}")
            #     corr_limt_hz = round(corr_limt_hz, 8)
                
            #     if abs(corr_limt_hz) >  Max_freq_limit:
            #         fraction_part = fraction_part *4
                    
            #     else:
            #         corr_outof_limit = False
            #         # send_freq_cmd(Req_corre) # Send command to Rb for frequency correction in Hz 
            #         send_freq_cmd(corr_limt_hz) # Send command to Rb for frequency correction in Hz 
                
            #     time.sleep(1)

        # elif abs(corr_limt_hz) < Min_freq_limit:

        #     corr_outof_limit = True # Correction applied is not in limits 
        #     multiply_part= 2 # mutiplier for the small correction to be applied  

        #     while corr_outof_limit:
                
        #         Req_corre = (-1.5* current_rb_hz)*multiply_part  # Required correction to compensate the slope 
        #         corr_limt_hz = Req_corre + current_rb_hz # corre_limt_hz is to cross check the anticipated position of the frequency offset after applying the corrections 


        #         if abs(corr_limt_hz) >  Max_freq_limit:
        #             multiply_part = multiply_part +2
                    
        #         else:
        #             corr_outof_limit = False
        #             # send_freq_cmd(Req_corre) # Send command to Rb for frequency correction in Hz 
        #             send_freq_cmd(corr_limt_hz) # Send command to Rb for frequency correction in Hz 
        

    # signal.clear()
    
    
# Create Flask app and SocketIO instance
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Function to emit TIC data to UI via WebSocket in JSON format
def send_tic_data(data):
    # Generate a timestamp in UTC
    timestamp = datetime.now(timezone.utc).isoformat()

    # Create the data in the desired format
    formatted_data = {
        'timestamp': timestamp,
        'value': data
    }

    # Emit the data as JSON
    socketio.emit('message', formatted_data)

    # Log the formatted data
    print(f"TIC Data: {formatted_data}")



# Flask route for testing
@app.route('/')
def home():
    return "Socket.IO server is running!"

# Flask WebSocket events
@socketio.on('connect')
def handle_connect():
    print("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

@socketio.on('applyPhaseCorrection')
def handle_phase_correction(data):
    try:
        # Extract the correction value and flag from the incoming WebSocket data
        corr_value = data.get('corrValue')
        flag = data.get('flag')
        print("data from frontend",data)                             
        
        if corr_value is None or flag is None:
            raise ValueError("Invalid data: 'corrValue' and 'flag' must be provided.")

        # Call the apply_Phase_correction function with the extracted data
        apply_Phase_correction(corr_value, flag)

        # Send a success response back to the client
        socketio.emit('phaseCorrectionStatus', {'status': 'success', 'value': corr_value})

    except Exception as e:
        # Handle any errors and send an error response
        socketio.emit('phaseCorrectionStatus', {'status': 'error', 'message': str(e)})



# Function to start the Flask app in a background thread
def start_flask_app():
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)



    
def steering_Rb():
    
    TIC_count1 =0 
    TIC_count2= 0
    first_phase_corr1 = True
    first_phase_corr2 = True
    TIC_slope= []
    data_to_save = []
    slope_counter=0
    steering = False # Auto loop the steering 
    steering_int = 30 # Steering interval is every 60 seconds 
    TIC_for_slope = []
    activate_steering = True
    steer_count = 0
    # Open the TIC serial port 
    time.sleep(1)
    TIC_ser = serial.Serial(port = 'COM14',baudrate = 115200 )
    print("TIC Comport is open: ", TIC_ser.isOpen())

    if not TIC_ser.isOpen():
        print("TIC Comport is not open")
        #TIC_ser.open()
        #print('COM5 is open', TIC_ser.isOpen())
    else:
        latest_readings = []
        TIC_4_slope = []
        
        error_record =[]

        # Wait for some time till the header files of the TIC lapsed & GNSS position fix is done for the receiver  
        time.sleep(15)   
        
        start_time= datetime.now()
        with open('TIC_data.csv', 'w', newline='') as csvfile:
            Column_name = ['Time stamp', 'TIC reading']
            writer = csv.DictWriter(csvfile, fieldnames = Column_name)
            writer.writeheader()
            
            
            while True:
                data = TIC_ser.readline().decode('utf-8').strip()
                print(f"TIC reading: f{data}")
                
                if data.__contains__("TI(A->B)"):
                    data1 = data.split(" ")
                    tic_reading = float(data1[0])
                    send_tic_data(tic_reading)  # Send TIC data via WebSocket
                    if float(data1[0])<1:
                        
                        nowt = datetime.now()
                        time_stamp = nowt.strftime("%d-%m-%Y %H:%M:%S")
                        
                        with open('TIC_data.csv', 'a', newline='') as csvfile:
                            Column_name = ['Time stamp', 'TIC reading']
                            writer = csv.DictWriter(csvfile, fieldnames = Column_name)
                            writer.writerow({'Time stamp':time_stamp, 'TIC reading': data1[0]})
                        
                        latest_readings.append(float(data1[0]))
                        
                        # If latest readings list has more than 5 entries, remove the oldest one
                        if len(latest_readings) > 3:
                            latest_readings.pop(0)    
                        
                        avg_reading =0
                        # Calculate and print the avervaluesprocess_CVage of the latest 3 readings
                        if latest_readings: 
                            avg_reading = sum(latest_readings) / len(latest_readings)
                            # read_count =read_count + 1 
                            print(f"Latest 3 readings average value in ns : {avg_reading*1E+9}")
                            error_UL = set_point - avg_reading
                        
                            # Check when to activate the CV mode 
                            error_record.append(error_UL)
                            
                          
                                
                            
                            if abs(avg_reading) > 80E-9: # UN LOCK condition # We can use this loop only once defining the limit to 100 ns
                                print(f"UNLOCK mode: More than 1 us : {TIC_count1}")
                                TIC_count2 = 0 
                                TIC_count1 = TIC_count1 +1 
                                # print(f"First Phase correction flag: f{first_phase_corr1}")
                                # Apply phase adjustment/ Offset adjustment 
                                # Initiate a parallel operaiton for Rb communication 
                                if first_phase_corr1: # First time pahse adjustment correction. 
                                    first_phase_corr1 = False
                                    # signal.set()
                                    apply_Phase_correction(avg_reading,0) # Inputs for this function are TIC reading in ns, binary 0 or 1: 0 indicates Phase adjustment 1 indicates Frequency adjustment
                                    print("Please wait for 20s till the next correction is applied")
                                    time.sleep(3)

                                if (TIC_count1 % 20) == 0 and not (first_phase_corr1) :
                                    print("UNLOCK mode: More than 1us applied correction after 20s ")
                                    # signal.set()
                                    apply_Phase_correction(avg_reading,1) # Inputs for this function are TIC reading in ns, binary 0 or 1: 0 indicates Phase adjustment 1 indicates Frequency adjustment
                                    time.sleep(3)

                           
                            elif abs(avg_reading) < 80E-9 and abs(avg_reading) > 1E-9:  # start auto steering when error is between 50 ns and 1 ns 
                             
                                steer_count = steer_count+1 
                                print(f"STEERING ACTIVATED, Steer count : {steer_count}")
                                TIC_for_slope.append(float(data1[0]))                        
                                if len(TIC_for_slope) > steering_int: # Every latest 60 s
                                    TIC_for_slope.pop(0)
                                
                                # if abs(avg_reading) > 1E-9:
                                    # activate_steering = True

                                #if ((count % steering_int ==0) & (len(freq_4_slope)  == steering_int)) :
                                if ((steer_count % steering_int == 0)):
                                    data_pointF = list(range(1, len(TIC_for_slope) + 1))
                                    slope, intercept = np.polyfit(data_pointF, TIC_for_slope,1) # y = mx + c ; ouput p = [m,c]
                                    print(f"Slope of the TIC_data (Frequency): {slope}")
                                    
                                  

                                    Freq_corr = 1.5*slope*1E+7
                                    phase_corr = ((0-float(data1[0]))*1E+7)/(phase_time_const) 


                                    print(f'Frequency Correction: {Freq_corr}')
                                    print(f'Phase Correction: {phase_corr}')
                                    
                                    Total_corr = -(Freq_corr - phase_corr)
                                    
                                    print(f"Total Correction applied: {Total_corr}")
                                    activate_steering = True # Keep the loop active for steering

                                    apply_Freq_correction(Total_corr,True) # Inputs is value of Rb currection in Hz and the flag to indicate the more of correction
                                                                     
                                    
                                    timestamp = datetime.now()

                                    # Append the data along with calculated values to the list
                                    data_to_save.append({
                                        'Timestamp': timestamp,
                                        'TIC reading': float(data1[0]),
                                        'Slope': slope,
                                        'Frequency Correction': Freq_corr,
                                        'Phase Correction': phase_corr,
                                        'Total Correction': Total_corr,
                                        'Phase Time Constant': phase_time_const,
                                        'Steering Interval': steering_int  # Replace with actual column name
                                    })

                                    # output_csv_path = 'F:\\qUARTZLOCK\\PYTHON\\Qz_Ster_overview.csv'  # Replace with your desired output CSV path
                                    # output_csv_path = r'F:\qUARTZLOCK\PYTHON\Qz_Ster_overview.csv'

                                    with open('Quarz_Ster_overview.csv', 'w', newline='') as csv_output:
                                        fieldnames = ['Timestamp', 'TIC reading','Slope','Frequency Correction', 'Phase Correction', 'Total Correction', 
                                                    'Phase Time Constant', 'Steering Interval']
                                        csv_writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
                                        
                                        csv_writer.writeheader()
                                        csv_writer.writerows(data_to_save)
                                                                            
                                    # apply_steering(CV_session, Present_error, Prev_error, time_bw_errors, correction_delay)


if __name__ == "__main__":
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=start_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    # Start TIC processing
    steering_Rb()
