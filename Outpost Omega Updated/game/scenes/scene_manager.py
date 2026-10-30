"""SceneManager: a stack of scenes (Menu, Level Select, Play, Pause, Win/Lose).

change(name) replaces the whole stack; push(name) puts an overlay on top
(the Pause menu draws over the frozen game). Only the top scene receives
input and updates; rendering starts from the topmost non-overlay scene.
"""


class Scene:
    is_overlay = False

    def __init__(self, game, **kwargs):
        self.game = game
        self.assets = game.assets
        self.audio = game.audio
        self.input = game.input

    # Hooks named after the pitch's OnStart / OnUpdate / OnRender
    def on_start(self):
        pass

    def on_exit(self):
        pass

    def on_resume(self):
        """Called when an overlay above this scene is popped."""
        pass

    def handle_command(self, cmd):
        pass

    def handle_event(self, event):
        for cmd in self.input.process(event):
            self.handle_command(cmd)

    def on_update(self, dt):
        pass

    def on_render(self, screen):
        pass


class SceneManager:
    def __init__(self, game):
        self.game = game
        self.factories = {}
        self.stack = []

    def register(self, name, factory):
        self.factories[name] = factory

    @property
    def top(self):
        return self.stack[-1] if self.stack else None

    def _make(self, name, kwargs):
        scene = self.factories[name](self.game, **kwargs)
        scene.name = name
        return scene

    def change(self, name, **kwargs):
        while self.stack:
            self.stack.pop().on_exit()
        scene = self._make(name, kwargs)
        self.stack.append(scene)
        scene.on_start()

    def push(self, name, **kwargs):
        scene = self._make(name, kwargs)
        self.stack.append(scene)
        scene.on_start()

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop().on_exit()
            self.top.on_resume()

    def handle_event(self, event):
        if self.top:
            self.top.handle_event(event)

    def on_update(self, dt):
        if self.top:
            self.top.on_update(dt)

    def on_render(self, screen):
        start = len(self.stack) - 1
        while start > 0 and self.stack[start].is_overlay:
            start -= 1
        for scene in self.stack[start:]:
            scene.on_render(screen)
