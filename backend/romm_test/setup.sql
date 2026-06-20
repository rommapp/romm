CREATE DATABASE IF NOT EXISTS romm_test;
CREATE USER IF NOT EXISTS 'romm_test'@'%' IDENTIFIED BY 'passwd';
-- Grant on *.* (not just romm_test.*) so the test user can create the
-- per-worker databases (romm_test_gw0, ...) used when running under pytest-xdist.
GRANT ALL PRIVILEGES ON *.* TO 'romm_test'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
