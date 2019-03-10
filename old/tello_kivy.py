import socket
import cv2
import threading

from kivy.app import App
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window

# TELLOとの通信設定
HOST_TELLO = '192.168.10.1'
PORT_CMD = 8889
HOST_LOCAL = '192.168.10.2'
PORT_STATE = 8890
PORT_VIDEO = 11111

# 画像表示用の変数
g_frame = None

# カメラ画像表示用クラス
class KivyCamera(Image):
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        # テクスチャを最大化するように設定
        self.allow_stretch = True
        # 更新間隔を設定
        Clock.schedule_interval(self.update, 1.0 / 30.0)

    def update(self, dt):
        global g_frame
        if g_frame is not None:
            # OpenCVの画像データをテクスチャに変換
            buf = cv2.flip(g_frame, 0).tostring()
            image_texture = Texture.create(size=(g_frame.shape[1], g_frame.shape[0]), colorfmt='bgr')
            image_texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
            # テクスチャを更新
            self.texture = image_texture

# アプリのクラス
class CamApp(App):
    axis_a = 0 # 左右軸
    axis_b = 0 # 前後軸
    axis_c = 0 # 高度軸
    axis_d = 0 # 回転角度

    def build(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.title = "Tello Camera"
        # ウィンドウサイズを設定
        Window.size = (960, 720)
        # ジョイスティックイベントを設定
        Window.bind(on_joy_axis=self.on_joy_axis)
        Window.bind(on_joy_button_down=self.on_joy_button_down)
        # 更新間隔を設定
        Clock.schedule_interval(self.update, 0.2)
        return KivyCamera()

    def on_stop(self):
        self.sock.close()

    def on_joy_axis(self, win, stickid, axisid, value):
        # PS3コントローラ(axisid)
        # 0:左スティック左右, 1:左スティック上下
        # 2:右スティック左右, 3:右スティック上下

        # 取得した値を-100/100の範囲内に調整
        value = 100 * value // 30000
        if value > 100:
            value = 100
        elif value < -100:
            value = -100

        # print('axis', stickid, axisid, value)
        if axisid == 0:
            self.axis_d = value
        elif axisid == 1:
            self.axis_c = -value
        elif axisid == 2:
            self.axis_a = value
        elif axisid == 3:
            self.axis_b = -value

    def on_joy_button_down(self, win, stickid, buttonid):
        # PS3コントローラ(buttonid)
        # 0:SELECT, 1:L3, 2:R3, 3:START
        # 4:上, 5:右, 6:下, 7:左
        # 8:L2, 9:R2, 10:L1, 11:R1
        # 12:△, 13:○, 14:×, 15:□

        # print('button_down', stickid, buttonid)
        if buttonid == 13:
            self.sock.sendto(b'takeoff', (HOST_TELLO, PORT_CMD))
        elif buttonid == 14:
            self.sock.sendto(b'land', (HOST_TELLO, PORT_CMD))

    def update(self, dt):
        cmd = 'rc {0} {1} {2} {3}'.format(self.axis_a, self.axis_b, self.axis_c, self.axis_d)
        # print(cmd.encode())
        self.sock.sendto(cmd.encode(), (HOST_TELLO, PORT_CMD))

# 画像取得スレッド
def capture_thread():
    global g_frame
    # ストリーミング受信準備
    addr = 'udp://' + HOST_LOCAL + ':' + str(PORT_VIDEO) + '?overrun_nonfatal=1&fifo_size=50000000'
    cap = cv2.VideoCapture(addr)
    while cap.isOpened():
        _, g_frame = cap.read()

# ステータス受信スレッド
def state_thread():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST_LOCAL, PORT_STATE))
    while True:
        data, _ = sock.recvfrom(1024)
        print(data.decode().rstrip('\r\n'))

if __name__ == '__main__':
    # SDKモード移行、ストリーミング開始
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(b'command', (HOST_TELLO, PORT_CMD))
    sock.sendto(b'streamon', (HOST_TELLO, PORT_CMD))
    sock.close()

    # 画像取得スレッドを立ち上げる
    th1 = threading.Thread(target=capture_thread)
    th1.daemon = True
    th1.start()

    # ステータス受信スレッドを立ち上げる
    th2 = threading.Thread(target=state_thread)
    th2.daemon = True
    th2.start()

    # アプリの起動
    CamApp().run()
