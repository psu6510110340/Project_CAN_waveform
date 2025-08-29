from decoder import CANDecoder
from serial_reader import SerialReader
import numpy as np
import time
from matplotlib import patches

BIT_DURATION = 20  # Duration of one bit in ticks (0.1 us/tick)

class Plotter:

    def __init__(self, app):

        self.decoder = CANDecoder()
        self.reader = None
        self.ax = None
        self.app = app

        self.frame_patches = []
        self.tooltip       = None
        self._cid          = None

        self.font_size = 9
        self.font_color = 'black'
        self.raw_data_log = []

        self.plot_timestamp = []

        self.frame_color = {"IDLE":"#45c0de", 
                            "IDLE ":"#45c0de",
                            "SOF":"#b1b6ba",
                            "ID":"#92c255",
                            "RTR":"#49b45d",
                            "r0":"#49b45d",
                            "r1":"#49b45d",
                            "SRR":"#49b45d",
                            "IDE":"#49b45d",
                            "BASE ID":"#92c255",
                            "EXT ID":"#92c255",
                            "DLC":"#00a765",
                            "Data":"#028fc3",
                            "CRC":"#b70032",
                            "CD":"#b70032",
                            "ACK":"#fbb900",
                            "AD":"#fbb900",
                            "EOF":"#ef7c00",
                            "IFS":"#757575"}
    
    def draw_idle_state(self, duration_bits=128):
        self.ax.clear()
        self.ax.set_ylim(-0.5, 1.5)
        self.ax.set_xlim(0, duration_bits * BIT_DURATION)
        self.ax.set_xlabel('Time (ticks)\n 0.1 us/tick')
        self.ax.set_ylabel('Logic level')
        self.ax.grid(True, axis='y')

        x = [0]
        y = [1]

        for i in range(duration_bits):
            start_x = i * BIT_DURATION
            end_x = (i + 1) * BIT_DURATION

            self.ax.axvspan(start_x, end_x, facecolor=self.frame_color["IDLE"], alpha=0.5)
            self.ax.axvline(x=end_x, color='gray', linestyle='-', linewidth=0.5)

            # Plot step line
            x.append(end_x)
            y.append(1)

            # Bit text
            self.ax.text(start_x + 10, -0.05, "1", fontsize=self.font_size, ha='center', va='center', color=self.font_color)

        # Field label "IDLE"
        self.ax.text(5, -0.43, "IDLE",
                    fontsize=self.font_size,
                    ha='left', va='baseline',
                    color='black',
                    bbox=dict(facecolor='yellow', edgecolor='black', boxstyle='round,pad=0.13'))

        self.ax.step(x, y, where='post', color='blue', linewidth=2)

    def start_read_data(self, port, baudrate):
        self.reader = SerialReader(port, baudrate)

    def bits_to_hex(self, bits):
        if len(bits) == 1:
            return bits
        elif bits:
            return f"0x{int(bits, 2):02X}"
        else: 
            return "0x00"

    def setup_graph(self):

        self.ax.clear()
        self.ax.set_ylim(-0.5, 1.5)
        self.ax.set_xlabel('Time (ticks)\n 0.1 us/tick')
        self.ax.set_ylabel('Logic Level')
        self.ax.grid(True, axis='y')

    def get_pos(self, bit_cnt, offset_bits=4):
        pos = 0
        act_bit_mins_4 = bit_cnt - offset_bits
        if bit_cnt > (offset_bits - 1) and (bit_cnt - offset_bits) * 2 < len(self.plot_timestamp):
            time_diff = self.plot_timestamp[act_bit_mins_4 * 2 + 1] - self.plot_timestamp[act_bit_mins_4 * 2]
            pos = self.plot_timestamp[act_bit_mins_4 * 2] + time_diff / 2 + offset_bits * BIT_DURATION
        elif (bit_cnt - offset_bits) * 2 >= len(self.plot_timestamp):
            cnt_from_last = bit_cnt - len(self.plot_timestamp) // 2
            pos = self.plot_timestamp[-1] + cnt_from_last * BIT_DURATION + 10
        else:
            pos = bit_cnt * BIT_DURATION + 10 
        
        return pos

    def draw_frame(self):

        self.setup_graph()

        last_timestamp = 0
        actual_bit_cnt = 0
        offset_bits = 4
        last_1bit_part_counter = 0

        bit_data = self.decoder.bit_data
        frames = self.decoder.retrived_frame
        stuff_bit_pos = self.decoder.stuff_bits_position

        self.plot_timestamp = self.decoder.retrive_bit_timestamp(self.decoder.timestamp_data)

        for frame_info in frames:
  
            x_pos = self.get_pos(actual_bit_cnt, offset_bits) 

            if self.app.frametype_chkbox.get():
                frame_type_label = f"Frame type: {frame_info['FrameType']} {frame_info['FrameSubtype']} Frame"
                self.ax.text(x_pos, 1.05, frame_type_label,
                            fontsize=12, fontweight='bold', verticalalignment='bottom',
                            horizontalalignment='left', color='black',
                            bbox=dict(facecolor='yellow', edgecolor='black', boxstyle='round,pad=0.13'))
            
            # add IDLE to frame info
            if actual_bit_cnt == 0:
                frame_info = {'IDLE': [1] * offset_bits, **frame_info}

            for part, bits in frame_info.items():
                
                if type(bits) == int:
                    bits = [bits]

                if part in ('FrameType', 'FrameSubtype') or len(bits) == 0:
                    continue

                x_pos = self.get_pos(actual_bit_cnt, offset_bits)
                bit_text = ''.join(str(b) for b in bits)
                bit_decoded = self.bits_to_hex(bit_text) if len(bits) > 1 else str(bits[0])

                if actual_bit_cnt - offset_bits in stuff_bit_pos:
                    x_pos += BIT_DURATION

                if self.app.hili_chkbox.get():
                    # draw part name
                    part_label = '\n'.join(part) if len(bits) == 1 else part
                    self.ax.text(
                        x_pos -5, -0.43 + last_1bit_part_counter * 0.1, part_label,
                        fontsize=self.font_size,
                        ha='left', va='baseline',
                        color='black',
                        bbox=dict(facecolor='yellow', edgecolor='black', boxstyle='round,pad=0.13')
                    )

                if self.app.hex_chkbox.get() and len(bits) > 1 and part not in ('IDLE', 'EOF', 'IFS', 'IDLE '):
                    # draw hex data of each part
                    self.ax.text(
                        x_pos -5, -0.48 + last_1bit_part_counter * 0.1, bit_decoded,
                        fontsize=self.font_size,
                        ha='left', va='baseline',
                        color='black',
                        bbox=dict(facecolor='yellow', edgecolor='black', boxstyle='round,pad=0.13')
                    )
                
                #draw Base ID + Ext ID -> ID
                if part == "BASE ID":
                    bit_text = ''.join(str(b) for b in frame_info['BASE ID']+frame_info['EXT ID'])
                    bit_decoded = self.bits_to_hex(bit_text)
                    last_1bit_part_counter += 1

                    if self.app.hex_chkbox.get():
                        # draw part name
                        self.ax.text(
                            x_pos -5, -0.45 + last_1bit_part_counter * 0.1, "ID :" + bit_decoded, 
                            fontsize=self.font_size,
                            ha='left', va='baseline',
                            color='black',
                            bbox=dict(facecolor="#ffe291", edgecolor='black', boxstyle='round,pad=0.13')
                        )
                    last_1bit_part_counter = 0
                
                for bit in bits:

                    if actual_bit_cnt - offset_bits in stuff_bit_pos:
                        x_pos = self.get_pos(actual_bit_cnt, offset_bits) 
                        
                        if self.app.text_chkbox.get():

                            # draw stuff text
                            self.ax.text(
                                x_pos, 0.5, 'stuff',
                                fontsize=self.font_size,
                                fontweight='bold',
                                ha='center',
                                va='center',
                                color='white',
                                rotation=90,
                                bbox=dict(facecolor='red', edgecolor='black', boxstyle='round,pad=0.2')
                            )
                        
                        if self.app.bit_chkbox.get():

                            # draw stuff bit 
                            self.ax.text(x_pos,  -0.05, bit_data[actual_bit_cnt - offset_bits], fontsize=self.font_size, ha='center', va='center', color=self.font_color)
                        
                        act_bit_mins_4 = actual_bit_cnt - offset_bits
                        t1 = self.plot_timestamp[act_bit_mins_4 * 2] + BIT_DURATION * offset_bits
                        t2 = self.plot_timestamp[act_bit_mins_4 * 2 + 1] + BIT_DURATION * offset_bits

                        if self.app.hili_chkbox.get():
                            self.ax.axvspan(t1, t2, facecolor='#ff6961', alpha=0.5)
                            
                        self.ax.axvline(t2, color='grey', linestyle='-', linewidth=0.5)

                        actual_bit_cnt += 1
                    
                    x_pos = self.get_pos(actual_bit_cnt, offset_bits)

                    if self.app.bit_chkbox.get():
                        # draw bit 
                        self.ax.text(x_pos,  -0.05, str(bit), fontsize=self.font_size, ha='center', va='center', color=self.font_color)
                    
                    act_bit_mins_4 = actual_bit_cnt - offset_bits
                    t1 = self.plot_timestamp[act_bit_mins_4 * 2] + 80 if actual_bit_cnt > 3 and act_bit_mins_4 * 2 < len(self.plot_timestamp) else 0
                    t2 = self.plot_timestamp[act_bit_mins_4 * 2 + 1] + 80 if actual_bit_cnt > 3 and act_bit_mins_4 * 2 < len(self.plot_timestamp) else 0
                    
                    color = self.frame_color['Data'] if part.startswith("Data") else self.frame_color[part]

                    if self.app.hili_chkbox.get():
                        # draw colored plane
                        if actual_bit_cnt > 3 and act_bit_mins_4 * 2 < len(self.plot_timestamp):
                            self.ax.axvspan(t1, t2, facecolor=color, alpha=0.5)
                            
                        else:
                            self.ax.axvspan(x_pos - 10, x_pos + 10, facecolor=color, alpha=0.5)
                            last_timestamp = x_pos + 10

                    if actual_bit_cnt > 3 and act_bit_mins_4 * 2 < len(self.plot_timestamp):
                        self.ax.axvline(t2, color='grey', linestyle='-', linewidth=0.5)
                        last_timestamp = t2
                    else:
                        self.ax.axvline(x_pos + 10, color='grey', linestyle='-', linewidth=0.5)
                        last_timestamp = x_pos + 10

                    actual_bit_cnt += 1

        x, y = self.decoder.get_plot_data()
           
        total_bits      = actual_bit_cnt + 1
        last_needed_ts  = (total_bits - offset_bits) * BIT_DURATION

        # add line at the end
        if y and last_needed_ts > y[-1]:
            y.append(last_needed_ts) 
            x.append(1)            

        # add line at the start
        start_offset = offset_bits * BIT_DURATION
        x = [1, 1] + x
        y = [0, start_offset] + [yi + start_offset for yi in y]

        self.ax.set_xlim(0, last_timestamp)
        
        self.ax.step(y, x, where='post', color='blue', linewidth=2)

    def update(self, frame):
        data = self.reader.read_data()

        if data:

            self.raw_data_log.append(data)

            if not self.decoder.decode_and_parse_data(data):
                return
            
            frame = self.decoder.retrived_frame[0] if self.decoder.retrived_frame else None

            if frame:

                if 'ID' in frame:
                    can_id_bin = ''.join(str(b) for b in frame['ID'])
                elif 'BASE ID' in frame:
                    can_id_bin = ''.join(str(b) for b in frame['BASE ID'] + frame['EXT ID'])
                else:
                    can_id_bin = None

                if can_id_bin:
                    can_id = int(can_id_bin, 2)
                    if can_id == 0x650:
                        self.app.disable_all_checkboxes()
                    else:
                        self.app.enable_all_checkboxes()

            self.draw_frame()
                    