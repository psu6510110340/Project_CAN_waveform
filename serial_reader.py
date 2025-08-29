import serial
import threading
import queue
import time


class SerialReader:
    def __init__(self, port, baudrate=1152000, chunk_size=1024):
        self.ser = serial.Serial(port, baudrate, timeout=1)
        self.chunk_size = chunk_size
        self._buf = queue.Queue()
        self._stop = threading.Event()

        self._thr = threading.Thread(target=self._loop, daemon=True)
        self._thr.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                if self.ser.in_waiting:
                    data = self.ser.read(self.chunk_size)
                    if data:
                        self._buf.put(data)
                else:
                    time.sleep(0.01)
            except Exception as e:
                print(f"[SerialReader] read error: {e}")
                break

    def read_data(self):
        out = b''
        while not self._buf.empty():
            out += self._buf.get_nowait()
        return out

    def disconnect(self):
        self._stop.set()
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                print("Serial port disconnected.")
            except Exception as e:
                print(f"Error closing port: {e}")
        if self._thr.is_alive():
            self._thr.join(timeout=1)
