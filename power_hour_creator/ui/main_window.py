import os
import platform
import subprocess

from PyQt5.QtCore import QObject, pyqtSignal, QSize, QPoint
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QHeaderView, QMessageBox, QApplication

from power_hour_creator import config
from power_hour_creator.media import PowerHour
from power_hour_creator.resources import image_path
from power_hour_creator.ui.exporting import export_power_hour_in_background, \
    get_power_hour_export_path
from power_hour_creator.ui.power_hour_list import PowerHourModel
from power_hour_creator.ui.tracklist import TrackDelegate, TracklistModel
from .forms.mainwindow import Ui_mainWindow

ERROR_DISPLAY_TIME_IN_MS = 5000
CREATED_DISPLAY_TIME_IN_MS = 10000


class MainWindow(QMainWindow, Ui_mainWindow):

    def __init__(self, power_hour_model, tracklist_model, tracklist_delegate,
                 track_error_dispatcher):
        super().__init__()
        self.power_hour_model = power_hour_model
        self.tracklist_model = tracklist_model
        self.tracklist_delegate = tracklist_delegate
        self.track_error_dispatcher = track_error_dispatcher
        self._settings = config.persistent_settings()

        self.setupUi(self)
        self._setup_power_hour_list_view()
        self._setup_tracklist()
        self._connect_create_power_hour_button()
        self._connect_track_errors()
        self._enable_create_power_hour_button_when_tracks_present()
        self._connect_help_menu()
        self._connect_file_menu()
        self._connect_power_hour_list_view()
        self.setWindowIcon(QIcon(image_path('Beer-80.png')))
        self._restore_view_settings()

    def _setup_power_hour_list_view(self):
        self.powerHoursListView.setModel(self.power_hour_model)
        self.powerHoursListView.setModelColumn(1)

        self.power_hour_model.rowsInserted.connect(self.powerHoursListView.select_new_power_hour)

    def _setup_tracklist(self):
        self._setup_tracklist_model()
        self._setup_tracklist_delegate()

    def _setup_tracklist_model(self):
        self.tracklist.setModel(self.tracklist_model)
        self.tracklist.hideColumn(0)  # id
        self.tracklist.hideColumn(1)  # position
        self.tracklist.hideColumn(7)  # power_hour_id

    def _setup_tracklist_delegate(self):
        self.tracklist.setItemDelegate(self.tracklist_delegate)

    def _connect_create_power_hour_button(self):
        self.createPowerHourButton.clicked.connect(self._export_power_hour)

    def _connect_track_errors(self):
        self.tracklist_model\
            .error_downloading\
            .connect(self._show_error_downloading)

        self.track_error_dispatcher\
            .track_invalid\
            .connect(self._show_track_error)

    def _show_error_downloading(self, url, error_message):
        self.statusBar.showMessage(
            'Error downloading "{}": {}'.format(url, error_message),
            ERROR_DISPLAY_TIME_IN_MS
        )

    def _show_track_error(self, error):
        if error['code'] == 'start_time_too_late':
            self.statusBar.showMessage(
                "Error: Start time {} is greater than the track's length"
                    .format(error['start_time']),
                ERROR_DISPLAY_TIME_IN_MS
            )
        elif error['code'] == 'start_time_format_bad':
            self.statusBar.showMessage(
                'Error: Start time "{}" is not in a usable format'
                    .format(error['start_time']),
                ERROR_DISPLAY_TIME_IN_MS
            )


    def _enable_create_power_hour_button_when_tracks_present(self):
        self.tracklist_model\
            .new_power_hour_selected\
            .connect(self._try_to_enable_create_button_on_tracklist_change)

        self.tracklist_model\
            .dataChanged\
            .connect(self._try_to_enable_create_button_on_tracklist_change)

        self._try_to_enable_create_button_on_tracklist_change()

    def _try_to_enable_create_button_on_tracklist_change(self):
        self.createPowerHourButton.setEnabled(self.tracklist_model.is_valid_for_export())

    def _show_worker_error(self, message):
        msg = QMessageBox(self)
        msg.setText('Error occured')
        msg.setDetailedText(message)
        msg.show()

    def _export_power_hour(self):
        power_hour_path = get_power_hour_export_path(
            parent=self,
            is_video=self._is_video_power_hour()
        )

        if power_hour_path:

            power_hour = PowerHour(
                tracks=self.tracklist_model.tracks,
                path=power_hour_path,
                is_video=self._is_video_power_hour(),
                name=self._current_power_hour_name()
            )

            export_power_hour_in_background(
                power_hour=power_hour,
                parent_widget=self,
                export_progress_view=self
            )

    def _is_video_power_hour(self):
        return self.videoCheckBox.checkState()

    def _show_power_hour_created(self):
        self.statusBar.showMessage(
            "Power hour created!", CREATED_DISPLAY_TIME_IN_MS)

    def _connect_help_menu(self):
        def show_logs():
            show_log_folder_in_file_browser()

        self.actionShow_logs.triggered.connect(show_logs)

    def _connect_file_menu(self):
        def new_power_hour():
            power_hour_id = self.power_hour_model.add_power_hour()
            self.tracklist_model.add_tracks_to_new_power_hour(power_hour_id)
            self.tracklist_model.show_tracks_for_power_hour(power_hour_id)

        self.actionNew_Power_Hour.triggered.connect(new_power_hour)

    def _connect_power_hour_list_view(self):
        def show_power_hour_name(new_index, _=None):
            ph_name = new_index.data()
            self.powerHourNameLabel.setText(ph_name)

        def show_renamed_power_hour_name(top_left_index, _):
            current_selection = self.powerHoursListView.selectionModel().selectedIndexes()
            if top_left_index in current_selection:
                show_power_hour_name(top_left_index)

        def show_this_power_hours_tracks(new_index, _):
            ph_id = new_index.sibling(new_index.row(), 0).data()
            self.tracklist_model.show_tracks_for_power_hour(ph_id)

        self.powerHoursListView.selectionModel().currentRowChanged.connect(show_power_hour_name)
        self.powerHoursListView.selectionModel().currentRowChanged.connect(show_this_power_hours_tracks)
        self.powerHoursListView.selectionModel().currentRowChanged.connect(self.tracklist.scrollToTop)

        self.powerHoursListView.model().dataChanged.connect(show_renamed_power_hour_name)

    def _current_power_hour_name(self):
        return self.powerHourNameLabel.text()

    def closeEvent(self, event):
        self._write_view_settings()

        event.accept()

    def _write_view_settings(self):
        self._settings.setValue('main_window/maximized', self.isMaximized())
        self._store_size_and_pos_unless_maximized()
        self._settings.setValue('splitter', self.splitter.saveState())

        self.tracklist.write_settings(self._settings)

    def _store_size_and_pos_unless_maximized(self):
        # https://stackoverflow.com/questions/74690/how-do-i-store-the-window-size-between-sessions-in-qt
        if not self.isMaximized():
            self._settings.setValue('main_window/size', self.size())
            self._settings.setValue('main_window/pos', self.pos())

    def _restore_view_settings(self):
        settings = self._settings

        self.resize(settings.value('main_window/size', QSize(800, 600)))
        self.move(settings.value('main_window/pos', QPoint(0, 0)))

        if settings.contains('splitter'):
            self.splitter.restoreState(settings.value('splitter'))

        self.tracklist.apply_settings(settings)

    def show_with_last_full_screen_setting(self):
        if self._settings.value('main_window/maximized') == 'true':
            self.showMaximized()
        else:
            self.show()


class TrackErrorDispatch(QObject):
    track_invalid = pyqtSignal(dict)


def build_main_window(parent):
    track_error_dispatcher = TrackErrorDispatch()
    return MainWindow(
        power_hour_model=PowerHourModel(parent=parent),
        tracklist_model=TracklistModel(parent=parent),
        tracklist_delegate=TrackDelegate(
            track_error_dispatcher=track_error_dispatcher
        ),
        track_error_dispatcher=track_error_dispatcher
    )


def show_log_folder_in_file_browser():
    if config.OS == 'windows':
        os.startfile(config.APP_DIRS.user_log_dir, 'explore')
    elif config.OS == 'darwin':
        subprocess.check_call(['open', config.APP_DIRS.user_log_dir])

