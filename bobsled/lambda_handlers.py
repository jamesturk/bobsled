from __future__ import print_function
from bobsled.status import check_status


def echo(event, context):
    print(event, context)


def check_status_handler(event, context):
    check_status(do_upload=True)
