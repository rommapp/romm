from logger.logger import log


def test_logger(caplog):
   log.debug("Testing debug message")
   assert "debug message" in caplog.text

   log.info("Testing info message")
   assert "info message" in caplog.text

   log.warning("Testing warning message")
   assert "warning message" in caplog.text

   log.error("Testing error message")
   assert "error message" in caplog.text

   log.critical("Testing critical message")
   assert "critical message" in caplog.text
