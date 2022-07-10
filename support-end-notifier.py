#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later

"""
Graphical notification system for pending end-of-support date for the OS

This program implements a notification system in the graphical session that will
issue a series of warnings starting a month before the date specified in the
SUPPORT_END= field in os-release(5) file.

It can be invoked in three modes:
– as a systemd generator (when invoked with a directory name as argument)
— with --notify, to display a message using the notification system of the
  graphical environment.
— with no arguments: the SUPPORT_END date will be displayed.

When the user clicks on the notification blurb, gnome-software or another tool
will be started.

$SUPPORT_END can be set in the environment to override the value in os-release.
"""

import argparse
import datetime
import os
import pathlib
import platform

WARN_DAYS = [30, 20, 10, 6, 5, 4, 3, 2, 1]

VERBOSE = os.getenv('DEBUG') == '1'

def argument_parser():
    parser = argparse.ArgumentParser(
        'support-end-notifier',
        formatter_class=argparse.RawTextHelpFormatter,
        description=__doc__,
        allow_abbrev=False)

    parser.add_argument('normal_dir', metavar='normal-dir', nargs='?',
                        type=pathlib.Path)
    parser.add_argument('early_dir', metavar='early-dir', nargs='?',
                        type=pathlib.Path)
    parser.add_argument('late_dir', metavar='late-dir', nargs='?',
                        type=pathlib.Path)
    parser.add_argument('--notify', action='store_true',
                        help='Actually display the notification')
    return parser

def support_end():
    val = os.getenv('SUPPORT_END')
    if not val:
        os_release = platform.freedesktop_os_release()
        val = os_release['SUPPORT_END']

    return datetime.datetime.strptime(val, '%Y-%m-%d')


### generator

def now():
    return datetime.datetime.today()

def generate_times(enddate):
    if enddate - now() < datetime.timedelta(days=1):
        yield f'OnActiveSec=60'
    else:
        for days in WARN_DAYS:
            time = enddate - datetime.timedelta(days=days)
            yield f'OnCalendar={time.isoformat()}'

def generate_units(enddate, dir):
    now = datetime.datetime.today()

    service = dir / 'support-end.service'
    with service.open('wt') as out:
        print('[Service]', file=out)
        print(f'ExecStart={__file__}', file=out)

    timer = dir / 'support-end.timer'
    with timer.open('wt') as out:
        print('[Timer]', file=out)

        for spec in generate_times(enddate):
            print('Got spec:', spec)
            print(spec, file=out)


### graphical notifier

def upgrade_callback(notification, action_name):
    print('Trying to start upgrade…')

    notification.close()

    # FIXME: does gnome-software have a mode where it can be launched
    # directly into a mode that starts an upgrade?
    os.execvp('gnome-software', ['gnome-software'])

    # FIXME: add other upgrade programs and patterns

def show_message(title, message=None):
    import gi
    gi.require_version('Notify', '0.7')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Notify, GLib

    Notify.init('support-end')
    notif = Notify.Notification.new(title,
                                    message or title,
                                    'dialog-warning')

    notif.add_action('clicked', 'Start upgrade',
                     upgrade_callback)

    notif.show()

    GLib.MainLoop().run()

def do_notify(enddate):
    now = datetime.datetime.today()

    if now > enddate:
        show_message('Support for this OS has ended')
    else:
        left = enddate - now
        show_message(f'Support for this OS ends in {left.days} days')


### main

def main():
    args = argument_parser().parse_args()

    try:
        enddate = support_end()
        exception = None
    except Exception as e:
        enddate = None
        exception = e

    if not args.notify and not args.normal_dir:
        # Show status

        if enddate:
            print('Found SUPPORT_END:', enddate)
            print(f'({enddate - now()} left)')
        else:
            print(f'No SUPPORT_END found: {exception!r}')

    elif args.notify and args.normal_dir:
        exit('No positional args are allowed with --notify')

    elif args.notify and enddate:
        do_notify(enddate)

    elif enddate:
        generate_units(enddate, args.normal_dir)

if __name__ == '__main__':
    main()
