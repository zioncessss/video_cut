# Data Model & Contracts: 重新合成全链路深度提速与管线优化

## Material Metadata Extension

在 `Material` 模型中延续元数据一致性，`is_hdr` 状态可按需缓存在素材元数据或进程内缓存。

```python
class Material(BaseModel):
    id: str
    category: MaterialCategory
    filename: str
    filepath: str
    duration: float = 0.0
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    is_hdr: Optional[bool] = None  # 记录是否为 HDR/HLG/BT2020 宽色域
```

## Composer Internal State

```python
class FFmpegFilterComposer:
    def __init__(self):
        self.has_ffmpeg: bool
        self._has_cas: Optional[bool]
        self._cached_encode_args: Optional[List[str]]
        # 缓存键为 (filepath, mtime)
        self._hdr_cache: Dict[str, bool] = {}
```
