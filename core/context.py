import threading
import queue
import time

from core.data.cache import GlobalMetadataCache

class AppContext:
    """
    应用程序全局上下文 (Singleton)。
    管理全局状态、锁、队列以及核心服务实例。
    替代原本散乱的 globals.py 和 extensions.py。
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppContext, cls).__new__(cls)
            cls._instance._init_state()
            cls._instance._init_components()
        return cls._instance

    def _init_state(self):
        """初始化基础状态变量、锁和队列"""
        
        # === 初始化状态 (原 init_status) ===
        # 用于前端轮询服务器启动进度
        self.init_status = {
            "status": "initializing", # initializing, processing, ready
            "message": "正在初始化...",
            "progress": 0,
            "total": 0
        }

        # === 扫描器状态 (原 scan_queue, scan_active) ===
        # 后台文件系统扫描队列
        self.scan_queue = queue.Queue()
        self.scan_active = False
        
        # === 扫描防抖 (原 _scan_debounce_*) ===
        # 防止短时间内大量文件变动触发多次全量扫描
        self.scan_debounce_lock = threading.Lock()
        self.scan_debounce_timer = None

        # === 并发控制 (原 thumb_semaphore) ===
        # 限制图片缩略图生成的并发数，防止 CPU/IO 过载 (默认 4)
        self.thumb_semaphore = threading.Semaphore(4)

        # === 缓存重载防抖 (原 _reload_*) ===
        # 0.5~1s 内多次 reload 请求合并为一次
        self.reload_lock = threading.Lock()
        self.reload_timer = None
        self.reload_pending = False
        self.reload_last_reason = ""

        # === 文件系统监听抑制 (原 _fs_ignore_*) ===
        # 当本程序主动修改文件时，抑制 watchdog 事件，避免死循环
        self.fs_ignore_until = 0.0
        self.fs_ignore_lock = threading.Lock()

        # === 世界书列表缓存 (原 wi_list_cache) ===
        # 避免频繁扫描磁盘读取大 JSON
        self.wi_list_cache = {}
        self.wi_list_cache_lock = threading.Lock()
        
        # === 全局元数据缓存 (原 metadata_cache) ===
        # 初始为 None，在 _init_components 中实例化
        self.cache = None

        # === 索引服务状态 ===
        self.index_lock = threading.Lock()
        self.index_job_lock = threading.Lock()
        self.index_state = {
            'state': 'empty',
            'scope': 'cards',
            'progress': 0,
            'message': '',
            'pending_jobs': 0,
        }
        self.index_worker_started = False

    def _init_components(self):
        """
        初始化复杂组件。
        """
        self.cache = GlobalMetadataCache()

    def set_status(self, status: str = None, message: str = None, progress: int = None, total: int = None):
        """辅助方法：更新应用启动状态"""
        if status is not None:
            self.init_status['status'] = status
        if message is not None:
            self.init_status['message'] = message
        if progress is not None:
            self.init_status['progress'] = progress
        if total is not None:
            self.init_status['total'] = total

    def update_fs_ignore(self, seconds: float = 1.5):
        """辅助方法：设置文件系统事件忽略时间窗口"""
        with self.fs_ignore_lock:
            self.fs_ignore_until = max(self.fs_ignore_until, time.time() + float(seconds))

    def should_ignore_fs_event(self) -> bool:
        """辅助方法：检查当前是否应该忽略文件系统事件"""
        with self.fs_ignore_lock:
            return time.time() < self.fs_ignore_until

# 全局单例实例
ctx = AppContext()
