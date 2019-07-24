import pickle as pk

from spawny import DaemonCouldNotSendMsgError, UnknownException


def test_picklable_exception_class():
    """Tests that our wrapper exception class can be pickled so that it can safely be sent over the Pipe"""
    pk.loads(pk.dumps(DaemonCouldNotSendMsgError.create_from(1, "hello", UnknownException(use_sys=False))))
