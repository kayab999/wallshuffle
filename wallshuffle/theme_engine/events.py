import weakref
import logging

class EventBus:
    def __init__(self):
        self.listeners = {}  # event -> list[weakref]
        self.logger = logging.getLogger(self.__class__.__name__)

    def on(self, event: str, callback):
        """Standard subscription."""
        # Use WeakMethod for instance methods to avoid reference cycles
        ref = weakref.WeakMethod(callback) if hasattr(callback, "__self__") else callback
        self.listeners.setdefault(event, []).append(ref)

    def once(self, event: str, callback):
        """Execute only once."""
        def wrapper(*args, **kwargs):
            self.off(event, wrapper)
            callback(*args, **kwargs)
        self.on(event, wrapper)

    def off(self, event: str, callback):
        """Safe unsubscribe."""
        if event in self.listeners:
            self.listeners[event] = [
                ref for ref in self.listeners[event]
                if (isinstance(ref, weakref.WeakMethod) and ref() != callback) or ref != callback
            ]
            if not self.listeners[event]:
                del self.listeners[event]

    def emit(self, event: str, *args, **kwargs):
        """Emit an event to all subscribers."""
        if event not in self.listeners:
            return

        # Clean up dead weakrefs while iterating
        active_listeners = []
        for ref in self.listeners.get(event, []):
            if isinstance(ref, weakref.WeakMethod):
                cb = ref()
                if cb is not None:
                    active_listeners.append(ref)
                    try:
                        cb(*args, **kwargs)
                    except Exception as e:
                        self.logger.error(f"Error in EventBus callback for {event}: {e}")
            else:
                active_listeners.append(ref)
                try:
                    ref(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error in EventBus callback for {event}: {e}")
        
        self.listeners[event] = active_listeners
