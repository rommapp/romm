CREATE DATABASE IF NOT EXISTS romm_test;
CREATE USER IF NOT EXISTS 'romm_test'@'%' IDENTIFIED BY 'passwd';
-- Grant on the `romm_test%` namespace (the base DB plus the per-worker
-- `romm_test_gw0`, ... databases created under pytest-xdist). A database-level
-- grant on a wildcard pattern also lets the user CREATE matching databases,
-- while confining it to that namespace on a shared instance. The `\_` escapes
-- the underscore so it is matched literally rather than as a single-char wildcard.
GRANT ALL PRIVILEGES ON `romm\_test%`.* TO 'romm_test'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
