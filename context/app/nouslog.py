import logging
import os



def log():

    """This is a basic custom logger that writes to the nous.log file as nouslog. To use this log in other modules, simply import this module and call the log function. """

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    nouslog = logging.FileHandler(os.path.join(os.path.abspath(('logs/nous.log'))),'a')
    #nouslog = logging.FileHandler(os.path.join(os.path.abspath(('/var/www/contextio/context/app/logs/nous.log'))),'a')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    nouslog.setFormatter(formatter)
    logger.addHandler(nouslog)
    return logger

if __name__ == "__main__":

    log()
