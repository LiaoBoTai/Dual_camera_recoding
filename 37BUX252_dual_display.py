import imagingcontrol4 as ic4
import cv2, time
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QSlider, QGroupBox, QFormLayout
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6 import QtCore, QtGui, QtWidgets


# -----------------------
# Advanced Control Panel
# -----------------------


class AdvancedPanel(QWidget):
    def __init__(self, property_map):
        super().__init__()
        self.property_map = property_map
        self.initUI()

    def initUI(self):
        layout = QFormLayout()
        # Example: Exposure Slider
        self.exposure_slider = QSlider(QtCore.Qt.Horizontal)
        self.exposure_slider.setMinimum(0)
        self.exposure_slider.setMaximum(100)
        self.exposure_slider.setValue(int(self.property_map[ic4.PropId.EXPOSURE_TIME  ].value))
        self.exposure_slider.valueChanged.connect(self.change_exposure)
        layout.addRow("Exposure", self.exposure_slider)

        # Example: Gain Slider
        self.gain_slider = QSlider(QtCore.Qt.Horizontal)
        self.gain_slider.setMinimum(0)
        self.gain_slider.setMaximum(100)
        self.gain_slider.setValue(int(self.property_map[ic4.PropId.GAIN].value))
        self.gain_slider.valueChanged.connect(self.change_gain)
        layout.addRow("Gain", self.gain_slider)

        self.setLayout(layout)

    def change_exposure(self, val):
        self.property_map.try_set_value(ic4.PropId.EXPOSURE_TIME, val)

    def change_gain(self, val):
        self.property_map.try_set_value(ic4.PropId.GAIN, val)

class MainWindow(QMainWindow):
    new_frame_0 = QtCore.Signal(object)
    new_frame_1 = QtCore.Signal(object)

    def __init__(self):
        QMainWindow.__init__(self)
        self.inc = 0
        self.window_w, self.window_h = 1080, 720
        self.scale = 0.58
        self.ocv = True
        self.recorderType = False
        self.last_update_time_0 = time.time()
        self.last_update_time_1 = time.time()

        device_list= ic4.DeviceEnum.devices()
        self.devices_0 = device_list[0]
        self.devices_1 = device_list[1]

        print(ic4.DeviceEnum.devices()[0])
        self.grabber_0 = ic4.Grabber(self.devices_0)
        self.grabber_1 = ic4.Grabber(self.devices_1)
        print(self.grabber_0)
        self.devices_0_property_map = self.grabber_0.device_property_map
        self.devices_1_property_map = self.grabber_1.device_property_map
        self.frame_rate = self.devices_0_property_map[ic4.PropId.ACQUISITION_FRAME_RATE].value
        self.video_writer_0 = ic4.VideoWriter(ic4.VideoWriterType.MP4_H264)
        self.video_writer_1 = ic4.VideoWriter(ic4.VideoWriterType.MP4_H264)
        # print(self.frame_rate)
        # print(self.video_writer)
        class Listener(ic4.QueueSinkListener):
            def __init__(self, video_writer: ic4.VideoWriter,frame_callback):
                self.frame_callback = frame_callback
                self.video_writer = video_writer
                self.counter = 0
                self.do_write_frames = False
                self.first_frame_arrived = False
            def sink_connected(self, sink: ic4.QueueSink, image_type: ic4.ImageType, min_buffers_required: int) -> bool:
                # No need to configure anything, just accept the connection
                self.image_type = image_type
                return True

            def frames_queued(self, sink: ic4.QueueSink):
                # Get the queued image buffer
		        # We have to remove buffers from the queue even if not recording; otherwise the device will not have
		        # buffers to write new video data into
                buffer = sink.pop_output_buffer()
                img = buffer.numpy_wrap()
                if self.frame_callback is not None:
                    self.frame_callback(img)

                if not self.first_frame_arrived:
                    self.first_frame_arrived = True
                    print("First frame arrived")

                if self.do_write_frames:
                    self.video_writer.add_frame(buffer)
                    self.counter = self.counter + 1

            def enable_recording(self, enable: bool):
                if enable:
                    self.counter = 0
                self.do_write_frames = enable

            def num_frames_written(self):
                return self.counter

        self.new_frame_0.connect(self.update_label_0)
        self.new_frame_1.connect(self.update_label_1)
        self.listener_0 = Listener(self.video_writer_0,frame_callback=lambda img: self.new_frame_0.emit(img))
        self.listener_1 = Listener(self.video_writer_1,frame_callback=lambda img: self.new_frame_1.emit(img))
        
        self.devices_0_property_map.try_set_value(ic4.PropId.WIDTH  , 1280)
        self.devices_0_property_map.try_set_value(ic4.PropId.HEIGHT , 720)
        self.devices_0_property_map.try_set_value(ic4.PropId.ACQUISITION_FRAME_RATE, 240)

        self.devices_1_property_map.try_set_value(ic4.PropId.WIDTH  , 1280)
        self.devices_1_property_map.try_set_value(ic4.PropId.HEIGHT , 720)
        self.devices_1_property_map.try_set_value(ic4.PropId.ACQUISITION_FRAME_RATE, 240)


        self.sink_0 = ic4.QueueSink(self.listener_0)
        self.sink_1 = ic4.QueueSink(self.listener_1)

        self.grabber_0.stream_setup(self.sink_0)
        self.grabber_1.stream_setup(self.sink_1)
        
        self.createUI()
        

        
        
        print("All Gd")


    def createUI(self):
        # Top: Video Display
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        video_layout = QtWidgets.QHBoxLayout()
        self.win1 = QtWidgets.QLabel('this is an image',self)
        self.win1.setMinimumSize(640, 480)
        self.win1.setAlignment(QtCore.Qt.AlignCenter)
        self.win1.setScaledContents(True)

        self.win2 = QtWidgets.QLabel('this is an image',self)
        self.win2.setMinimumSize(640, 480)
        self.win2.setAlignment(QtCore.Qt.AlignCenter)
        self.win2.setScaledContents(True)

        video_layout.addWidget(self.win1)
        video_layout.addWidget(self.win2)

        # Bottom: Advanced Panel
        tabs = QTabWidget()
        self.advanced_panel_0 = AdvancedPanel(self.devices_0_property_map)
        self.advanced_panel_1 = AdvancedPanel(self.devices_1_property_map)
        tabs.addTab(self.advanced_panel_0, "Camera 0 Controls")
        tabs.addTab(self.advanced_panel_1, "Camera 1 Controls")

        # Recording Buttons
        btn_layout = QHBoxLayout()
        self.btn_record = QPushButton("Record")
        self.btn_stop = QPushButton("Stop")
        self.btn_record.clicked.connect(self.recordVideo)
        self.btn_stop.clicked.connect(self.stopRecordVideo)
        btn_layout.addWidget(self.btn_record)
        btn_layout.addWidget(self.btn_stop)

        main_layout.addLayout(video_layout)
        main_layout.addWidget(tabs)
        main_layout.addLayout(btn_layout)


    def _update_label(self,label, frame):
        
        if not self.ocv  :  return
        # IC4 / OpenCV 是 BGR，Qt 要 RGB
        frame_rgb = cv2.cvtColor(frame[:, :, 0], cv2.COLOR_BayerRG2BGR)
        h, w, ch = frame_rgb.shape
        qimg = QtGui.QImage(frame_rgb.data, w, h, ch*w, QtGui.QImage.Format_RGB888)
        label.setPixmap(QtGui.QPixmap.fromImage(qimg))
        # pix = QtGui.QPixmap.fromImage(qimg)
        # pix = pix.scaled(
        #     label.size(),
        #     QtCore.Qt.KeepAspectRatio,
        #     QtCore.Qt.SmoothTransformation
        # )
        # label.setPixmap(pix)

    def update_label_0(self, frame):
        if time.time() - self.last_update_time_0 < 1/24:return
        self.last_update_time_0 = time.time()
        self._update_label(self.win1, frame)
    def update_label_1(self, frame):
        if time.time() - self.last_update_time_1 < 1/24:return
        self.last_update_time_1 = time.time()
        self._update_label(self.win2, frame)
        pass

    def closeEvent(self, ev: QCloseEvent):
        self.ocv = False
        if self.grabber_0.is_streaming:
            self.grabber_0.stream_stop()
        if self.grabber_1.is_streaming:
            self.grabber_1.stream_stop()
    
    def recordVideo(self):
        if not self.listener_0.first_frame_arrived:
            print("Stream not ready yet")
            return
        if self.recorderType == True:  self.stopRecordVideo()
        self.recorderType = True
        file_name_0 = f"video_{self.inc}_0.mp4"
        file_name_1 = f"video_{self.inc}_1.mp4"
        self.inc+=1
        
        self.video_writer_0.begin_file(file_name_0, self.sink_0.output_image_type, self.frame_rate )
        self.video_writer_1.begin_file(file_name_1, self.sink_1.output_image_type, self.frame_rate )
        self.listener_0.enable_recording(True)
        self.listener_1.enable_recording(True)
        print(f"Recording started")
        # self.btn2.setText('錄影中，點擊停止並存擋')
        
    def stopRecordVideo(self):
        self.listener_0.enable_recording(False)
        self.listener_1.enable_recording(False)
        self.video_writer_0.finish_file()
        self.video_writer_1.finish_file()
        
        print(f"L1 Wrote {self.listener_0.num_frames_written()} frames.")
        print(f"L2 Wrote {self.listener_1.num_frames_written()} frames.")
        print(f"Saved video file .")
        # self.btn2.setText('錄影')
        # self.btn2.setText('錄影')
        self.recorderType = False





if __name__ == "__main__":
    ic4.Library.init(api_log_level=ic4.LogLevel.INFO, log_targets=ic4.LogTarget.STDERR)

    try:
        app = QApplication()
        app.setApplicationName("ic4-simple")
        app.setApplicationDisplayName("IC4 Test Application")
        app.setStyle("fusion")
        app.setStyleSheet("""
            QMainWindow { background-color: #2E3440; }
            QLabel { color: #ECEFF4; font-size: 14px; }
            QPushButton { background-color: #5E81AC; color: white; border-radius: 6px; padding: 5px 15px; font-weight: bold; }
            QPushButton:hover { background-color: #81A1C1; }
            QSlider::groove:horizontal { height: 8px; background: #4C566A; border-radius: 4px; }
            QSlider::handle:horizontal { background: #88C0D0; width: 18px; border-radius: 9px; margin: -5px 0; }
            QTabBar::tab { background: #4C566A; color: #D8DEE9; padding: 8px 15px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #5E81AC; }
            QGroupBox { border: 2px solid #88C0D0; border-radius: 8px; margin-top: 20px; color: #ECEFF4; font-weight: bold; }
        """)
        w = MainWindow()
        w.show()
        app.exec()
        # example_imagebuffer_numpy_opencv_live()
    finally:
        ic4.Library.exit()
