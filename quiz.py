import cv2
import json
import random
import socket
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.text import DEFAULT_FONT, LabelBase
from kivy.core.window import Window
from kivy.graphics.texture import Texture
from kivy.properties import StringProperty
from kivy.uix.image import Image
from kivy.uix.widget import Widget

# GUIテストモード用のフラグ
TEST_GUI = True
CAM_ID = 0

# 音楽再生をコマンドで実行するフラグ
IS_USE_MPG123 = True

# TELLOとの通信設定
HOST_TELLO = '192.168.10.1'
PORT_CMD = 8889
HOST_LOCAL = '192.168.10.2'
PORT_STATE = 8890
PORT_VIDEO = 11111

# ステータス取得用のフラグ
GET_STATUS = False

# 画像表示用の変数
g_frame = None
g_display = None

# クイズ用の変数
g_question = None
g_answer = None
g_result = None
g_gameover = None
g_clear = None

# クイズの設定
QUIZ_NUM_MAX = 5
QUIZ_TIMER = 60 * 5


# カメラ画像表示用クラス
class TelloCamera(Image):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # テクスチャを最大化するように設定
        self.allow_stretch = True
        # 更新間隔を設定
        Clock.schedule_interval(self.update, 1.0 / 30.0)
        # BGMの再生
        if IS_USE_MPG123:
            import subprocess
            subprocess.Popen(['mpg123', '-Z', 'bgm.mp3'])
        else:
            sound = SoundLoader.load('bgm.mp3')
            if sound:
                sound.play()

    def update(self, dt):
        global g_display

        if g_display is not None:
            # OpenCVの画像データをテクスチャに変換
            frame = g_display
            buf = cv2.flip(frame, 0).tostring()
            image_texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            image_texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
            # テクスチャを更新
            self.texture = image_texture


# クイズ表示用クラス
class QuizWidget(Widget):
    text_question = StringProperty()
    text_timer = StringProperty()
    timer = QUIZ_TIMER
    quiz_all = None
    quiz_data = None
    quiz_genre = 0
    quiz_num = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        f = open('quiz.json', 'r', encoding='utf-8')
        self.quiz_all = json.load(f)
        self.quiz_data = self.quiz_all[self.quiz_genre]
        self._init_timer()
        self._update_quiz()
        Clock.schedule_interval(self.on_countdown, 1.0)

    def on_countdown(self, dt):
        global g_display
        global g_answer
        global g_result
        global g_gameover
        global g_clear

        if g_display is not None:
            # タイマー表示を更新する
            self.timer -= 1
            if self.timer > 0:
                self.text_timer = f'残り{self.timer}秒'
            else:
                g_gameover = True

            # クイズの結果を判定する
            if g_result is None:
                return
            elif g_result is True:
                self.quiz_num += 1
                if self.quiz_num >= QUIZ_NUM_MAX:
                    g_clear = True
                    return
                self.quiz_data = self.quiz_all[self.quiz_num]

            # クイズ用の変数をリセット
            g_answer = None
            g_result = None
            self._update_quiz()

    def _init_timer(self):
        # タイマーを初期化する
        self.timer = QUIZ_TIMER
        self.text_timer = f'残り{self.timer}秒'

    def _update_quiz(self):
        # 問題文・回答を更新する
        global g_question
        num = random.randint(0, len(self.quiz_data) - 1)
        g_question = self.quiz_data[num]['answer']
        self.text_question = self.quiz_data[num]['question']


# アプリのクラス
class QuizApp(App):
    axis_a = 0  # 左右軸
    axis_b = 0  # 前後軸
    axis_c = 0  # 高度軸
    axis_d = 0  # 回転角度

    def build(self, **kwargs):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.title = 'True/False Quiz of drone.'
        # ウィンドウサイズを設定
        Window.size = (960, 720)
        # キーボードイベントを設定
        Window.bind(on_key_down=self.on_key_down)
        # ジョイスティックイベントを設定
        Window.bind(on_joy_axis=self.on_joy_axis)
        Window.bind(on_joy_button_down=self.on_joy_button_down)
        # 更新間隔を設定
        Clock.schedule_interval(self.update, 0.2)
        return super().build(**kwargs)

    def on_stop(self):
        self.sock.close()

    def on_key_down(self, win, key, keycode, codepoint, modifier):
        if keycode == 40:
            self._set_relust()

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
        elif buttonid == 15:
            self._set_relust()

    def _set_relust(self):
        global g_question
        global g_answer
        global g_result
        if g_answer is not None:
            g_result = g_answer is g_question

    def update(self, dt):
        cmd = 'rc {0} {1} {2} {3}'.format(self.axis_a, self.axis_b, self.axis_c, self.axis_d)
        # print(cmd.encode())
        self.sock.sendto(cmd.encode(), (HOST_TELLO, PORT_CMD))


# 画像取得スレッド
def capture_thread():
    global g_frame
    if TEST_GUI:
        # GUIテストモードはカメラを使う
        cap = cv2.VideoCapture(CAM_ID)
    else:
        # ストリーミング受信準備
        addr = 'udp://' + HOST_LOCAL + ':' + str(PORT_VIDEO) + '?overrun_nonfatal=1&fifo_size=50000000'
        cap = cv2.VideoCapture(addr)
    while cap.isOpened():
        _, frame = cap.read()
        if frame is None:
            continue
        g_frame = frame


# 画像処理スレッド
def image_process_thread():
    global g_frame
    global g_display
    global g_answer
    global g_result

    # カスケード分類器
    cascade1 = cv2.CascadeClassifier('Circle_cascade.xml')
    cascade2 = cv2.CascadeClassifier('Cross_cascade.xml')
    cascade3 = cv2.CascadeClassifier('Plus_cascade.xml')

    while True:
        if g_frame is None:
            # 画像取得前は1秒スリープする
            time.sleep(1)
        else:
            frame = g_frame
            answer = None
            max_area = 0
            # フレーム画像をグレースケールに変換
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 格納されたフレームに対してカスケードファイルに基づいて Circle を検知
            circle = cascade1.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
            for (x, y, w, h) in circle:
                area = w * h
                if max_area < area:
                    answer = True
                    max_area = area
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3, cv2.LINE_AA)

            # 格納されたフレームに対してカスケードファイルに基づいて Cross を検知
            cross = cascade2.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
            for (x, y, w, h) in cross:
                area = w * h
                if max_area < area:
                    answer = False
                    max_area = area
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 3, cv2.LINE_AA)

            # 格納されたフレームに対してカスケードファイルに基づいて Plus を検知
            plus = cascade3.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
            for (x, y, w, h) in plus:
                area = w * h
                if max_area < area:
                    answer = False
                    max_area = area
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 3, cv2.LINE_AA)

            # 現在の回答選択状況を表示
            g_answer = answer
            if answer is True:
                cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 255, 0), 3, cv2.LINE_AA)
            elif answer is False:
                cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 255), 3, cv2.LINE_AA)

            # 現在の正解状況を表示
            if g_result is True:
                size = min(frame.shape[:1])//2-50
                cv2.circle(frame, (frame.shape[1]//2, frame.shape[0]//2), size, (0, 255, 0), 30)
            elif g_result is False:
                size = min(frame.shape[:1])//2-50
                x0 = frame.shape[1]//2 - size
                x1 = frame.shape[1]//2 + size
                y0 = frame.shape[0]//2 - size
                y1 = frame.shape[0]//2 + size
                cv2.line(frame, (x0, y0), (x1, y1), (0, 0, 255), 30)
                cv2.line(frame, (x1, y0), (x0, y1), (0, 0, 255), 30)

            # 画像表示用の変数に結果を設定
            g_display = frame


# ステータス受信スレッド
def state_thread():
    if TEST_GUI:
        # GUIテストモードはステータス受信しない
        return
    if not GET_STATUS:
        # フラグなし時はステータス受信しない
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST_LOCAL, PORT_STATE))
    while True:
        data, _ = sock.recvfrom(1024)
        print(data.decode().rstrip('\r\n'))


if __name__ == '__main__':
    LabelBase.register(DEFAULT_FONT, 'ipaexg.ttf')

    if not TEST_GUI:
        # SDKモード移行、ストリーミング開始
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b'command', (HOST_TELLO, PORT_CMD))
        sock.sendto(b'streamon', (HOST_TELLO, PORT_CMD))
        sock.close()

    # 画像取得スレッドを立ち上げる
    th1 = threading.Thread(target=capture_thread)
    th1.daemon = True
    th1.start()

    # 画像処理スレッドを立ち上げる
    th2 = threading.Thread(target=image_process_thread)
    th2.daemon = True
    th2.start()

    # ステータス受信スレッドを立ち上げる
    th3 = threading.Thread(target=state_thread)
    th3.daemon = True
    th3.start()

    # アプリの起動
    QuizApp().run()
