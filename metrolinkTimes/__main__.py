from tornado.ioloop import IOLoop

from metrolinkTimes.metrolinkTimes import Application


def main():
    mlApplication = Application
    io_loop = IOLoop.current()
    io_loop.run_sync(mlApplication.run)


if __name__ == '__main__':
    main()
