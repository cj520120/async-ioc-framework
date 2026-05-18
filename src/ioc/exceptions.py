class CircularDependencyError(Exception):
    pass


class MissingDependencyError(Exception):
    pass


class BeanCreationError(Exception):
    pass


class SchedulerError(Exception):
    pass


class AmbiguousDependencyError(Exception):
    pass
