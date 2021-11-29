from typing import Any, Optional, List, Callable, cast, Dict


OnSuccessCallback = Callable[[Any], None]
OnErrorCallback = Callable[[Exception], None]


class DeferredValue:
    PENDING = -1
    REJECTED = 0
    RESOLVED = 1

    _value: Optional[Any]
    _reason: Optional[Exception]
    _callbacks: List[OnSuccessCallback]
    _errbacks: List[OnErrorCallback]

    def __init__(
        self,
        on_complete: Optional[OnSuccessCallback] = None,
        on_error: Optional[OnErrorCallback] = None,
    ):
        self._state = self.PENDING
        self._value = None
        self._reason = None
        if on_complete:
            self._callbacks = [on_complete]
        else:
            self._callbacks = []
        if on_error:
            self._errbacks = [on_error]
        else:
            self._errbacks = []

    def resolve(self, value: Any) -> None:
        if self._state != DeferredValue.PENDING:
            return

        if isinstance(value, DeferredValue):
            value.add_callback(self.resolve)
            value.add_errback(self.reject)
            return

        self._value = value
        self._state = self.RESOLVED

        callbacks = self._callbacks
        self._callbacks = []
        for callback in callbacks:
            try:
                callback(value)
            except Exception:
                # Ignore errors in callbacks
                pass

    def reject(self, reason: Exception) -> None:
        if self._state != DeferredValue.PENDING:
            return

        self._reason = reason
        self._state = self.REJECTED

        errbacks = self._errbacks
        self._errbacks = []
        for errback in errbacks:
            try:
                errback(reason)
            except Exception:
                # Ignore errors in errback
                pass

    def then(
        self,
        on_complete: Optional[OnSuccessCallback] = None,
        on_error: Optional[OnErrorCallback] = None,
    ) -> "DeferredValue":
        ret = DeferredValue()

        def call_and_resolve(v: Any) -> None:
            try:
                if on_complete:
                    ret.resolve(on_complete(v))
                else:
                    ret.resolve(v)
            except Exception as e:
                ret.reject(e)

        def call_and_reject(r: Exception) -> None:
            try:
                if on_error:
                    ret.resolve(on_error(r))
                else:
                    ret.reject(r)
            except Exception as e:
                ret.reject(e)

        self.add_callback(call_and_resolve)
        self.add_errback(call_and_resolve)

        return ret

    def add_callback(self, callback: OnSuccessCallback) -> None:
        if self._state == self.PENDING:
            self._callbacks.append(callback)
            return

        if self._state == self.RESOLVED:
            callback(self._value)

    def add_errback(self, callback: OnErrorCallback) -> None:
        if self._state == self.PENDING:
            self._errbacks.append(callback)
            return

        if self._state == self.REJECTED:
            callback(cast(Exception, self._reason))

    @property
    def is_resolved(self) -> bool:
        return self._state == self.RESOLVED

    @property
    def is_rejected(self) -> bool:
        return self._state == self.REJECTED

    @property
    def value(self) -> Any:
        return self._value

    @property
    def reason(self) -> Optional[Exception]:
        return self._reason


def deferred_dict(m: Dict[str, Any]) -> DeferredValue:
    """
    A special function that takes a dictionary of deferred values
    and turns them into a deferred value that will ultimately resolve
    into a dictionary of values.
    """
    if len(m) == 0:
        raise TypeError("Empty dict")

    ret = DeferredValue()

    plain_values = {
        key: value for key, value in m.items() if not isinstance(value, DeferredValue)
    }
    deferred_values = {
        key: value for key, value in m.items() if isinstance(value, DeferredValue)
    }

    count = len(deferred_values)

    def handle_success(_: Any) -> None:
        nonlocal count
        count -= 1
        if count == 0:
            value = plain_values

            for k, p in deferred_values.items():
                value[k] = p.value

            ret.resolve(value)

    for p in deferred_values.values():
        p.add_callback(handle_success)
        p.add_errback(ret.reject)

    return ret


def deferred_list(l: List[Any]) -> DeferredValue:
    """
    A special function that takes a list of deferred values
    and turns them into a deferred value for a list of values.
    """
    if len(l) == 0:
        raise TypeError("Empty list")

    ret = DeferredValue()

    plain_values = {}
    deferred_values = {}
    for index, value in enumerate(l):
        if isinstance(value, DeferredValue):
            deferred_values[index] = value
        else:
            plain_values[index] = value

    count = len(deferred_values)

    def handle_success(_: Any) -> None:
        nonlocal count
        count -= 1
        if count == 0:
            values = []

            for k in sorted(list(plain_values.keys()) + list(deferred_values.keys())):
                value = plain_values.get(k, None)
                if not value:
                    value = deferred_values[k].value
                values.append(value)
            ret.resolve(values)

    for p in l:
        p.add_callback(handle_success)
        p.add_errback(ret.reject)

    return ret
