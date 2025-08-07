"""
Performance management and optimization for workflow system.
Provides caching, lazy loading, and performance monitoring.
"""

import time
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import defaultdict
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread


@dataclass
class PerformanceMetric:
    """Performance metric data"""
    name: str
    value: float
    unit: str
    timestamp: float
    
    
class PerformanceMonitor(QObject):
    """Monitors and tracks performance metrics"""
    
    metric_updated = pyqtSignal(object)  # PerformanceMetric
    
    def __init__(self):
        super().__init__()
        self.metrics = {}
        self.metric_history = defaultdict(list)
        self.enabled = True
        
    def record_metric(self, name: str, value: float, unit: str = "ms"):
        """Record a performance metric"""
        if not self.enabled:
            return
            
        metric = PerformanceMetric(name, value, unit, time.time())
        self.metrics[name] = metric
        self.metric_history[name].append(metric)
        
        # Keep only last 100 measurements
        if len(self.metric_history[name]) > 100:
            self.metric_history[name] = self.metric_history[name][-100:]
            
        self.metric_updated.emit(metric)
        
    def start_timer(self, name: str) -> float:
        """Start timing an operation"""
        start_time = time.time()
        self.metrics[f"{name}_start"] = start_time
        return start_time
        
    def end_timer(self, name: str) -> float:
        """End timing an operation and record the duration"""
        if f"{name}_start" in self.metrics:
            start_time = self.metrics[f"{name}_start"]
            duration = (time.time() - start_time) * 1000  # Convert to ms
            self.record_metric(name, duration, "ms")
            del self.metrics[f"{name}_start"]
            return duration
        return 0
        
    def get_average_metric(self, name: str, last_n: int = 10) -> Optional[float]:
        """Get average value for a metric over last N measurements"""
        if name not in self.metric_history:
            return None
            
        recent_metrics = self.metric_history[name][-last_n:]
        if not recent_metrics:
            return None
            
        return sum(m.value for m in recent_metrics) / len(recent_metrics)
        
    def get_metric_trend(self, name: str, window_size: int = 10) -> str:
        """Get trend direction for a metric"""
        if name not in self.metric_history or len(self.metric_history[name]) < window_size:
            return "unknown"
            
        recent = self.metric_history[name][-window_size:]
        mid_point = len(recent) // 2
        
        first_half = sum(m.value for m in recent[:mid_point]) / mid_point
        second_half = sum(m.value for m in recent[mid_point:]) / (len(recent) - mid_point)
        
        if second_half > first_half * 1.1:
            return "increasing"
        elif second_half < first_half * 0.9:
            return "decreasing"
        else:
            return "stable"


class TemplateCache:
    """High-performance cache for templates with LRU eviction"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.cache = {}
        self.access_order = []
        self.hit_count = 0
        self.miss_count = 0
        
    def get(self, key: str) -> Any:
        """Get item from cache"""
        if key in self.cache:
            self.hit_count += 1
            # Move to end (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        else:
            self.miss_count += 1
            return None
            
    def put(self, key: str, value: Any):
        """Put item in cache"""
        if key in self.cache:
            # Update existing
            self.cache[key] = value
            self.access_order.remove(key)
            self.access_order.append(key)
        else:
            # Add new
            if len(self.cache) >= self.max_size:
                # Evict least recently used
                lru_key = self.access_order.pop(0)
                del self.cache[lru_key]
                
            self.cache[key] = value
            self.access_order.append(key)
            
    def clear(self):
        """Clear the cache"""
        self.cache.clear()
        self.access_order.clear()
        
    def get_hit_rate(self) -> float:
        """Get cache hit rate"""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0
        
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'hit_rate': self.get_hit_rate()
        }


class LazyLoader:
    """Lazy loading utility for expensive operations"""
    
    def __init__(self):
        self.loaded_items = {}
        self.loading_items = set()
        self.load_callbacks = defaultdict(list)
        
    def load_async(self, key: str, loader_func, callback=None):
        """Load item asynchronously"""
        if key in self.loaded_items:
            if callback:
                callback(self.loaded_items[key])
            return
            
        if key in self.loading_items:
            if callback:
                self.load_callbacks[key].append(callback)
            return
            
        self.loading_items.add(key)
        if callback:
            self.load_callbacks[key].append(callback)
            
        # Start loading in background thread
        thread = threading.Thread(target=self._load_worker, args=(key, loader_func))
        thread.daemon = True
        thread.start()
        
    def _load_worker(self, key: str, loader_func):
        """Worker function for background loading"""
        try:
            result = loader_func()
            self.loaded_items[key] = result
            
            # Notify callbacks
            for callback in self.load_callbacks[key]:
                try:
                    callback(result)
                except Exception as e:
                    print(f"Error in lazy load callback for {key}: {e}")
                    
        except Exception as e:
            print(f"Error loading {key}: {e}")
        finally:
            self.loading_items.discard(key)
            if key in self.load_callbacks:
                del self.load_callbacks[key]
                
    def get_sync(self, key: str, loader_func):
        """Get item synchronously (blocks if not loaded)"""
        if key in self.loaded_items:
            return self.loaded_items[key]
            
        result = loader_func()
        self.loaded_items[key] = result
        return result
        
    def is_loaded(self, key: str) -> bool:
        """Check if item is loaded"""
        return key in self.loaded_items
        
    def is_loading(self, key: str) -> bool:
        """Check if item is currently loading"""
        return key in self.loading_items


class CanvasOptimizer:
    """Optimizations for canvas rendering and interaction"""
    
    def __init__(self, canvas):
        self.canvas = canvas
        self.viewport_cache = {}
        self.last_viewport_update = 0
        self.update_throttle_ms = 16  # ~60 FPS
        
    def optimize_viewport_updates(self):
        """Optimize viewport updates using throttling"""
        current_time = time.time() * 1000
        if current_time - self.last_viewport_update < self.update_throttle_ms:
            return False
            
        self.last_viewport_update = current_time
        return True
        
    def get_visible_items(self):
        """Get only items visible in current viewport"""
        if not hasattr(self.canvas, 'custom_scene') or not self.canvas.custom_scene:
            return []
        scene = self.canvas.custom_scene
            
        viewport_rect = self.canvas.mapToScene(self.canvas.viewport().rect()).boundingRect()
        return scene.items(viewport_rect)
        
    def optimize_node_rendering(self, node):
        """Optimize individual node rendering"""
        # Use level-of-detail rendering based on zoom level
        transform = self.canvas.transform()
        scale_factor = transform.m11()  # Get scale factor
        
        if scale_factor < 0.5:
            # Very zoomed out - use simplified rendering
            self._set_node_detail_level(node, "low")
        elif scale_factor < 1.0:
            # Moderately zoomed out - medium detail
            self._set_node_detail_level(node, "medium")
        else:
            # Normal or zoomed in - full detail
            self._set_node_detail_level(node, "high")
            
    def _set_node_detail_level(self, node, level: str):
        """Set node detail level for rendering optimization"""
        if hasattr(node, 'set_detail_level'):
            node.set_detail_level(level)
        elif hasattr(node, 'label'):
            # Simple optimization - hide labels when zoomed out
            if level == "low":
                node.label.setVisible(False)
            else:
                node.label.setVisible(True)
                
    def batch_updates(self, update_func, items: List):
        """Batch multiple updates together"""
        if not hasattr(self.canvas, 'custom_scene') or not self.canvas.custom_scene:
            # Fallback: execute updates individually without batching
            for item in items:
                update_func(item)
            return
        
        scene = self.canvas.custom_scene
        # Disable scene updates during batch
        if hasattr(scene, 'setUpdatesEnabled'):
            scene.setUpdatesEnabled(False)
            
        try:
            for item in items:
                update_func(item)
        finally:
            # Re-enable updates
            if hasattr(scene, 'setUpdatesEnabled'):
                scene.setUpdatesEnabled(True)
                scene.update()
                
    def batch_scene_changes(self, operations: List[callable]):
        """Batch multiple scene operations to minimize redraws"""
        if not operations:
            return
            
        # Block signals and updates during batch operations
        if not hasattr(self.canvas, 'custom_scene') or not self.canvas.custom_scene:
            # Fallback: execute operations individually without batching
            for operation in operations:
                try:
                    operation()
                except Exception as e:
                    print(f"Error in fallback operation: {e}")
            return
        scene = self.canvas.custom_scene
            
        if hasattr(scene, 'blockSignals'):
            scene.blockSignals(True)
        if hasattr(scene, 'setUpdatesEnabled'):
            scene.setUpdatesEnabled(False)
            
        try:
            # Execute all operations
            for operation in operations:
                try:
                    operation()
                except Exception as e:
                    print(f"Error in batch operation: {e}")
        finally:
            # Re-enable everything and trigger single update
            if hasattr(scene, 'blockSignals'):
                scene.blockSignals(False)
            if hasattr(scene, 'setUpdatesEnabled'):
                scene.setUpdatesEnabled(True)
                scene.update()
                
    def optimize_viewport_culling(self):
        """DISABLED - Viewport culling was counterproductive"""
        # This optimization was removed because profiling showed it was taking 120.26ms
        # and was counterproductive for performance. Canvas now renders all items.
        pass
                
    def enable_smart_invalidation(self):
        """Enable smart scene invalidation to minimize redraws"""
        if not hasattr(self.canvas, 'custom_scene') or not self.canvas.custom_scene:
            return
        scene = self.canvas.custom_scene
        if not hasattr(scene, 'invalidate'):
            return
            
        # Override scene invalidation to be more selective
        original_invalidate = scene.invalidate
        
        def smart_invalidate(rect=None, layers=None):
            # Only invalidate if viewport culling allows it
            if self.optimize_viewport_updates():
                original_invalidate(rect, layers)
                
        scene.invalidate = smart_invalidate


class MemoryManager:
    """Memory management for workflow components"""
    
    def __init__(self):
        self.tracked_objects = {}
        self.cleanup_callbacks = []
        
    def track_object(self, key: str, obj: Any, cleanup_func=None):
        """Track an object for memory management"""
        self.tracked_objects[key] = {
            'object': obj,
            'cleanup': cleanup_func,
            'created': time.time()
        }
        
    def cleanup_object(self, key: str):
        """Clean up a tracked object"""
        if key in self.tracked_objects:
            tracked = self.tracked_objects[key]
            if tracked['cleanup']:
                try:
                    tracked['cleanup'](tracked['object'])
                except Exception as e:
                    print(f"Error cleaning up {key}: {e}")
            del self.tracked_objects[key]
            
    def cleanup_old_objects(self, max_age_seconds: float = 300):
        """Clean up objects older than specified age"""
        current_time = time.time()
        to_cleanup = []
        
        for key, tracked in self.tracked_objects.items():
            if current_time - tracked['created'] > max_age_seconds:
                to_cleanup.append(key)
                
        for key in to_cleanup:
            self.cleanup_object(key)
            
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics"""
        import sys
        
        total_objects = len(self.tracked_objects)
        oldest_object = None
        
        if self.tracked_objects:
            oldest_time = min(tracked['created'] for tracked in self.tracked_objects.values())
            oldest_object = time.time() - oldest_time
            
        return {
            'tracked_objects': total_objects,
            'oldest_object_age': oldest_object,
            'python_objects': len(gc.get_objects()) if 'gc' in sys.modules else 0
        }


class WorkflowPerformanceManager(QObject):
    """Main performance management coordinator"""
    
    performance_report = pyqtSignal(dict)  # Performance metrics report
    
    def __init__(self):
        super().__init__()
        self.monitor = PerformanceMonitor()
        self.template_cache = TemplateCache(max_size=200)
        self.lazy_loader = LazyLoader()
        self.memory_manager = MemoryManager()
        self.canvas_optimizer = None
        
        # Setup periodic reporting
        self.report_timer = QTimer()
        self.report_timer.timeout.connect(self._generate_performance_report)
        self.report_timer.start(5000)  # Report every 5 seconds
        
    def set_canvas(self, canvas):
        """Set the canvas for optimization"""
        self.canvas_optimizer = CanvasOptimizer(canvas)
        
    def optimize_template_loading(self, template_registry):
        """Optimize template loading with caching"""
        original_get = template_registry.get_template
        
        def cached_get_template(template_id):
            # Check cache first
            cached = self.template_cache.get(template_id)
            if cached is not None:
                return cached
                
            # Load template and cache it
            self.monitor.start_timer(f"template_load_{template_id}")
            template = original_get(template_id)
            self.monitor.end_timer(f"template_load_{template_id}")
            
            if template:
                self.template_cache.put(template_id, template)
                
            return template
            
        # Replace the original method
        template_registry.get_template = cached_get_template
        
    def optimize_canvas_rendering(self):
        """Apply canvas rendering optimizations"""
        if not self.canvas_optimizer:
            return
            
        canvas = self.canvas_optimizer.canvas
        
        # Enable smart scene invalidation
        self.canvas_optimizer.enable_smart_invalidation()
        
        # Viewport culling optimization removed - was counterproductive
            
        # Set up scale change optimization  
        if hasattr(canvas, 'scaleChanged'):
            canvas.scaleChanged.connect(self._on_scale_changed)
        
    def batch_canvas_operations(self, operations: List[callable]):
        """Public method to batch canvas operations for performance"""
        if self.canvas_optimizer:
            self.canvas_optimizer.batch_scene_changes(operations)
            
    def trigger_viewport_optimization(self):
        """DISABLED - Viewport optimization was counterproductive"""
        # This method is disabled because viewport culling was removed
        pass
        
    def _on_scale_changed(self):
        """Handle scale/zoom changes"""
        if self.canvas_optimizer:
            # Update level-of-detail for all nodes (viewport culling removed)
            if hasattr(self.canvas_optimizer.canvas, 'nodes'):
                for node in self.canvas_optimizer.canvas.nodes:
                    self.canvas_optimizer.optimize_node_rendering(node)
        
        # Override paint events for optimization
        original_paint = canvas.paintEvent
        
        def optimized_paint(event):
            if self.canvas_optimizer.optimize_viewport_updates():
                self.monitor.start_timer("canvas_paint")
                original_paint(event)
                self.monitor.end_timer("canvas_paint")
                
        canvas.paintEvent = optimized_paint
        
    def _generate_performance_report(self):
        """Generate periodic performance report"""
        report = {
            'timestamp': time.time(),
            'canvas_paint_avg': self.monitor.get_average_metric("canvas_paint", 10),
            'template_cache_stats': self.template_cache.get_stats(),
            'memory_stats': self.memory_manager.get_memory_usage(),
            'performance_trends': {
                'canvas_paint': self.monitor.get_metric_trend("canvas_paint"),
            }
        }
        
        self.performance_report.emit(report)
        
    def get_optimization_recommendations(self) -> List[str]:
        """Get performance optimization recommendations"""
        recommendations = []
        
        # Check cache hit rate
        cache_stats = self.template_cache.get_stats()
        if cache_stats['hit_rate'] < 0.7:
            recommendations.append("Consider increasing template cache size for better hit rate")
            
        # Check canvas paint performance
        avg_paint_time = self.monitor.get_average_metric("canvas_paint", 10)
        if avg_paint_time and avg_paint_time > 16:  # 60 FPS threshold
            recommendations.append("Canvas painting is slow - consider reducing visual complexity")
            
        # Check memory usage
        memory_stats = self.memory_manager.get_memory_usage()
        if memory_stats['tracked_objects'] > 1000:
            recommendations.append("High number of tracked objects - consider cleanup")
            
        if not recommendations:
            recommendations.append("Performance is within acceptable ranges")
            
        return recommendations


# Import gc for memory tracking
try:
    import gc
except ImportError:
    gc = None