#!/usr/bin/python
#
# ------------------------------------------------------------
# daily-email.py
#
# J. Brusey, December 2011
#
# run a set of status queries but only send a message out when
# something significant happens.
#
# Report query methods can be found in cogent/report/*
#
# TODO fix bug where email is empty
# ------------------------------------------------------------


import os
import pickle
import platform
import smtplib
import time
from pathlib import Path

from sqlalchemy import create_engine

from cogent.base.model import Base, Session, init_model
from cogent.report import reports

TIMEOUT = 2 * 60  # 2 minutes

DBURL = "mysql://{user}@localhost/{database}?connect_timeout=1"

DEFAULT_AUTH_PATH = "/home/chuser/auth2.pickle"
AUTH_ENV_VAR = "COGENT_GMAIL_AUTH_PATH"
AUTH_PATH = os.environ.get(AUTH_ENV_VAR, DEFAULT_AUTH_PATH)


def mail(
    serverURL=None,
    sender="",
    to="",
    text="",
    login="",
    passwd="",
    debug=False,
    port=587,
):
    """
    Usage:
        mail('somemailserver.com', 'me@example.com', 'someone@example.com', 'test', 'This is a test')
    """
    #    headers = "From: {}\r\nTo: {}\r\nSubject: {}\r\n\r\n".format(sender, to, subject)
    #    message = headers + text
    mailServer = smtplib.SMTP(serverURL, port=port, timeout=TIMEOUT)
    mailServer.starttls()
    if debug:
        mailServer.set_debuglevel(True)
    if login != "":
        mailServer.login(login, passwd)
    mailServer.sendmail(sender, to, text)
    mailServer.quit()


def mail_string_list_to_gmail(to, error_list):
    with open(AUTH_PATH, "rb") as auth_file:
        auth = pickle.load(auth_file)
    if len(error_list) > 0:
        # text = '\n\n'.join(error_list)
        mail(
            serverURL="smtp.gmail.com",
            sender=auth[0],
            login=auth[0],
            passwd=auth[1],
            to=to,
            text=error_list,
        )


def header(you=None, me=None, host=None):
    return "From: {host}<{me}>\r\nTo: {you}\r\nMIME-Version: 1.0\r\nContent-type: text/html\r\nSubject: cogent-house status for {host}\r\n\r\n<html><head></head><body>".format(
        host=host, me=me, you=you
    )


def footer():
    return "</body></html>"


def run_reports(
    dry_run=False,
    time_queries=False,
    you="nobody@localhost",
    me="yield@" + platform.node(),
    host=platform.node(),
):
    try:
        session = Session()

        if time_queries:
            start_time = time.time()

        html = []
        for report, method in reports:
            html.extend(method(session))
            if time_queries:
                html.append(
                    "<p>%s took: %ld secs</p>" % (report, time.time() - start_time)
                )
                start_time = time.time()

    #        if len(html) == 0:
    #            html = ['No status updates to report']

    finally:
        session.close()

    message = header(you=you, me=me, host=host) + "".join(html) + footer()

    if dry_run:
        if len(html) == 0:
            print("Dry run: no email will be sent")
        else:
            print(message)
    else:
        # Send the message via local SMTP server.

        if len(html) > 0:
            mail_string_list_to_gmail(you, message)


#            s = smtplib.SMTP('localhost')
#            s.sendmail(me, you, message)

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option(
        "-n",
        "--dry-run",
        action="store_true",
        default=False,
        help="don't send e-mail--just print to stdout",
    )
    parser.add_option(
        "-t",
        "--time-queries",
        action="store_true",
        default=False,
        help="time how long each query takes",
    )
    parser.add_option("-d", "--database", default="ch", help="mysql database to use")
    parser.add_option(
        "-u", "--user", default="chuser", help="mysql user to login to database with"
    )
    parser.add_option(
        "-m", "--mailto", default="chuser@localhost", help="Address to send emails to"
    )

    parser.add_option(
        "-a",
        "--auth-file",
        dest="auth_file",
        help=(
            "Path to the Gmail credential pickle file. Overrides the"
            f" ${AUTH_ENV_VAR} environment variable."
        ),
    )

    (options, args) = parser.parse_args()

    resolved_auth_path = (
        options.auth_file
        or os.environ.get(AUTH_ENV_VAR)
        or DEFAULT_AUTH_PATH
    )

    auth_path = Path(resolved_auth_path)

    if not auth_path.is_file():
        parser.exit(
            status=1,
            msg=(
                f"Gmail credential file not found at '{auth_path}'. "
                f"Provide --auth-file or set ${AUTH_ENV_VAR}.\n"
            ),
        )

    AUTH_PATH = str(auth_path)

    engine = create_engine(
        DBURL.format(user=options.user, database=options.database), echo=False
    )
    Base.metadata.create_all(engine)
    init_model(engine)

    run_reports(
        dry_run=options.dry_run, time_queries=options.time_queries, you=options.mailto
    )
