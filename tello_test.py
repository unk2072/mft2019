import socket
import cv2
import threading
import time

HOST_TELLO = '192.168.10.1'
PORT_CMD = 8889
HOST_LOCAL = '192.168.10.2'
PORT_VIDEO = 11111

# 画像表示用の変数
g_frame = None

# ストリーミングの取得
def capture_thread():
    global g_frame
    while cap.isOpened():
        _, g_frame = cap.read()

# UDP通信開始
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# SDKモードに移行
client.sendto(b'command', (HOST_TELLO, PORT_CMD))

# ストリーミング開始
client.sendto(b'streamon', (HOST_TELLO, PORT_CMD))

# ストリーミング受信準備
addr = 'udp://' + HOST_LOCAL + ':' + str(PORT_VIDEO) + '?overrun_nonfatal=1&fifo_size=50000000'
cap = cv2.VideoCapture(addr)

# 画像処理スレッドを立ち上げる
th = threading.Thread(target=capture_thread)
th.daemon = True
th.start()

# FPS計算用の変数を初期化
base_t = time.perf_counter()
current_t = 0
cnt = 0

# 受信した画像を表示
while cap.isOpened():
    if g_frame is not None:
        cv2.imshow("frame", g_frame)
    # ESCキーでプログラムを終了
    if cv2.waitKey(10) == 27:
        break
    # FPSを計算する
    current_t = time.perf_counter()
    cnt += 1
    dt = current_t - base_t
    if dt > 1.0:
        base_t = current_t
        fps = cnt / dt 
        cnt = 0
        print('fps = %.2f' % fps)

cv2.destroyAllWindows()
cap.release()
