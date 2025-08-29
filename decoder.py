import struct
import numpy as np

class CANDecoder:
    def __init__(self, bit_duration=20, offset=8):
        self.bit_data = []
        self.timestamp_data = []
        self.state_data = []
        self.retrived_frame = []
        self.unstuff_bits = []
        self.stuff_bits_position = []

        self.bit_duration = bit_duration
        self.offset = offset
        self.last_time = 0

    def decode_and_parse_data(self, data):
        self.decode_8byte_data(data)
        self.unstuff_bits, self.stuff_bits_position = self.remove_stuff_bits(self.bit_data)
        self.retrived_frame = self.decode_frame_type(self.unstuff_bits)
        return self.bit_data

    def get_plot_data(self):
        return self.state_data, self.timestamp_data

    def reset_data(self):
        self.state_data.clear()
        self.timestamp_data.clear()
        self.bit_data.clear()
        self.total_time = 0
        self.last_time = 0

    def decode_8byte_data(self, raw_data):
        i = 0

        while i < len(raw_data):

            if raw_data[i:i+3] == b'\x11\x00\x01' or raw_data[i:i+3] == b'\x11\x01\x01':
                record = raw_data[i:i+8]
                if len(record) < 8:
                    continue

                state = record[1]
                if len(self.state_data) > 1 and state == self.state_data[-1]:
                    i += 8
                    continue

                timestamp = struct.unpack("<I", record[4:8])[0]
            
                # Debugging output
                # print(f"Rec: {record[0:4]}          {record[4:8]}           Lev: {state}    Dur: {timestamp}")
                
                if len(self.timestamp_data) > 0 and timestamp < self.timestamp_data[-1]:
                    self.reset_data()

                if timestamp > 3150:
                    break

                if len(self.state_data) >= 1:
                    self.state_data.append(self.state_data[-1])
                    self.timestamp_data.append(timestamp)
                    
                self.state_data.append(state)
                self.timestamp_data.append(timestamp)

                duration = timestamp - self.last_time

                while duration > self.offset:
                    self.bit_data.append(1 - state)
                    duration -= self.bit_duration
                    pass

                self.last_time = timestamp
                
                i += 8
            else:
                i += 1

    def decode_frame_type(self, bits):
        frames = []
        current_idx = 0

        while current_idx < len(bits):

            frame_info = {}
            try:
                if bits[current_idx] == 1:
                    break
                
                # SOF is bit 0
                frame_info['SOF'] = bits[current_idx]
                current_idx += 1  

                # IDE (bit 13) and RTR (bit 12 for standard)
                ide_bit = bits[current_idx + 12]
                rtr_bit = bits[current_idx + 11]

                if ide_bit == 0:
                    # Standard Frame (11-bit ID)
                    frame_info['FrameType'] = 'Standard'
                    frame_info['ID'] = bits[current_idx:current_idx+11]
                    current_idx += 11
                    frame_info['RTR'] = bits[current_idx]
                    current_idx += 1
                    frame_info['IDE'] = bits[current_idx]
                    current_idx += 1
                    frame_info['r0'] = bits[current_idx]
                    current_idx += 1

                else:
                    # Extended Frame (29-bit ID)
                    frame_info['FrameType'] = 'Extended'
                    frame_info['BASE ID'] = bits[current_idx:current_idx+11]
                    current_idx += 11
                    frame_info['SRR'] = bits[current_idx]
                    current_idx += 1
                    frame_info['IDE'] = bits[current_idx]
                    current_idx += 1
                    frame_info['EXT ID'] = bits[current_idx:current_idx+18]
                    current_idx += 18
                    frame_info['RTR'] = bits[current_idx]
                    rtr_bit = bits[current_idx]
                    current_idx += 1
                    frame_info['r0'] = bits[current_idx]
                    current_idx += 1
                    frame_info['r1'] = bits[current_idx]
                    current_idx += 1

                # DLC (always next 4 bits)
                frame_info['DLC'] = bits[current_idx:current_idx+4]
                current_idx += 4

                dlc_value = int(''.join(str(b) for b in frame_info['DLC']), 2)
                
                # Check for Remote Frame
                if rtr_bit == 1:
                    frame_info['FrameSubtype'] = 'Remote'
                    # frame_info['Data'] = []
                else:
                    frame_info['FrameSubtype'] = 'Data'
                    # Read data bytes (8 bits per byte)
                    for i in range(dlc_value):
                        frame_info[f'Data{i}'] = bits[current_idx:current_idx+8]
                        current_idx += 8
                    # current_idx += dlc_value*8

                if len(bits[current_idx:current_idx+15]) < 5:
                    print("CRC bits not enough")
                    frames.append(frame_info)
                    break

                while len(bits[current_idx:current_idx+15]) < 15:
                    bits.append(1)
                # CRC (next 15 bits after data)
                frame_info['CRC'] = bits[current_idx:current_idx+15]
                current_idx += 15

                while current_idx >= len(bits):
                    bits.append(1)
                    
                frame_info['CD'] = bits[current_idx]

                while current_idx+1 >= len(bits):
                    bits.append(1)
                    
                frame_info['ACK'] = bits[current_idx+1]

                while current_idx+2 >= len(bits):
                    bits.append(1)
                    
                frame_info['AD'] = bits[current_idx+2]

                while current_idx+10 >= len(bits):
                    bits.append(1)
                
                frame_info['EOF'] = bits[current_idx+3:current_idx+10]
                current_idx += 10  # Move past EOF

                while current_idx+3 >= len(bits):
                    bits.append(1)
                
                frame_info['IFS'] = bits[current_idx:current_idx+3]
                current_idx += 3  # Move past IFS
                

                if current_idx+4 >= len(bits):
                    while current_idx+4 >= len(bits):
                        bits.append(1)
                    
                    frame_info['IDLE '] = bits[current_idx:current_idx+4]
                    current_idx += 4  # Move past Idle

            except Exception as e:
                print(f"Error decoding frame: {e}")
                break
            
            frames.append(frame_info)
            
        print("finished decoding frames")
        return frames
    
    def retrive_bit_timestamp(self, timestamp_data):
        actual_bit_timestamp = []
        for time_index in range(0, len(timestamp_data)-1,2):
            t1 = timestamp_data[time_index]
            t2 = timestamp_data[time_index + 1] 
            time_diff = t2 - t1
            bit_count = 0

            while time_diff > 20:
                bit_count += 1
                time_diff -= 20
            if time_diff > 8:
                bit_count += 1

            for i in np.arange(t1, t2, (t2 - t1) / bit_count):
                actual_bit_timestamp.append(i)
                actual_bit_timestamp.append(i + (t2 - t1) / bit_count)

        actual_bit_timestamp[0] = 0

        return actual_bit_timestamp
    
    def remove_stuff_bits(self, bitstream):
        un_stf_bits = [bitstream[0]]
        stf_bit_pos = []

        last_bit = bitstream[0]
        cnt = 1
        bit_cnt = 0

        for bit in bitstream[1:]:
            bit_cnt += 1
            if bit == last_bit:
                cnt += 1
                un_stf_bits.append(bit)
            else:
                if cnt == 5:
                    cnt = 1
                    # add stuff bit position to list
                    stf_bit_pos.append(bit_cnt)
                else:
                    cnt = 1
                    un_stf_bits.append(bit)

            last_bit = bit

        return un_stf_bits, stf_bit_pos