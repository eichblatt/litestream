class ScreenContext():
    NONE = 0
    COMPOSER = 1
    GENRE = 2
    WORK = 3
    PERFORMANCE = 4
    TRACKLIST = 5
    FAVORITES = 6
    OTHER = 7

class GeneralContext:
    def __init__(self):
        self.player = None
        self.state = None
        self.keyed_work = None
        self.selected_work = None
        self.selected_composer = None
        self.keyed_composer = None
        self.selected_genre = None
        self.keyed_genre = None
        self.selected_performance = None
        self.tracklist = []
        self.track_titles = []
        self.performance_index = 0
        self.worklist = []
        self.worklist_key = None
        self.worklist_index = 0
        self.last_update_time = 0
        self.play_pause_press_time = 0
        self.select_press_time = 0
        self.power_press_time = 0
        self.ycursor = 0
        self.SCREEN = ScreenContext.NONE
        self.prev_SCREEN = ScreenContext.NONE
        self.HAS_TOKEN = False
        
    def __repr__(self):
        items = [
            f"player: {self.player}",
            f"state: {self.state}",
            f"keyed_work: {self.keyed_work}",
            f"selected_work: {self.selected_work}",
            f"selected_composer: {self.selected_composer}",
            f"keyed_composer: {self.keyed_composer}",
            f"selected_genre: {self.selected_genre}",
            f"keyed_genre: {self.keyed_genre}", 
            f"selected_performance: {self.selected_performance}",
            f"tracklist: {self.tracklist}",
            f"track_titles: {self.track_titles}",
            f"performance_index: {self.performance_index}",
            f"worklist: {self.worklist}",
            f"worklist_key: {self.worklist_key}",
            f"worklist_index: {self.worklist_index}",
            f"last_update_time: {self.last_update_time}",
            f"play_pause_press_time: {self.play_pause_press_time}",
            f"select_press_time: {self.select_press_time}",
            f"power_press_time: {self.power_press_time}",
            f"ycursor: {self.ycursor}",
            f"SCREEN: {self.SCREEN}",
            f"prev_SCREEN: {self.prev_SCREEN}",
            f"HAS_TOKEN: {self.HAS_TOKEN}"
        ]
        return "GeneralContext:\n" + "\n".join(items)

glc = GeneralContext()
glc.SCREEN = ScreenContext.NONE