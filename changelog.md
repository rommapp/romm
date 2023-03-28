# v1.3 (_29-03-2023_)

## Fixed
**`Breaking change`** - **This breaking change only applies for mariaDB users**:

Some users reported errors when scanning files with large names because filenames are limited to 100 characters in the database. As I want to give as much flexibility as possible I changed some database columns. 

If you didn't make a lot of manual changes you can just get rid of the database and recreate it, scanning your library again. If you did some changes and don't want to lose the progress, you should do this changes manually from the mariadb container (or wherever you have your mariadb database) since there is not any kind of CLI for this migration.

I am so sorry for any inconvenience this can generate.

Columns to modify (examples in case that you set it with database name as romm, in other case just change the database name in the {db_name}.roms part):
 - alter table romm.roms modify column filename varchar(500);
 - alter table romm.roms modify column filename_no_ext varchar(500);
 - alter table romm.roms modify column name varchar(500);
 - alter table romm.roms modify column r_slug varchar(500);
 - alter table romm.roms modify column p_slug varchar(500);
 - alter table romm.roms modify column path_cover_l text;
 - alter table romm.roms modify column path_cover_s text;
 - alter table romm.platforms modify column slug varchar(500);
 - alter table romm.platforms modify column name varchar(500);
 - alter table romm.platforms modify column path_logo text;


# v1.2.2 (_28-03-2023_)

## Added
 - Notification added when downloading a game

## Changed
 - Database name when using mariadb now can be changed with the new variable DB_NAME. Check [docker-compos.example.yml](https://github.com/zurdi15/romm/blob/master/docker/docker-compose.example.yml)

## Fixed
 - Potential password error when using mariadb if the password have special characters
 - Some other bugs

# v1.2 (_28-03-2023_)

## Added
 - SQLite support
 - Dreamcast support (https://github.com/zurdi15/romm#platforms-support)

## Changed
 - SQLite is now the database by default if ROMM_DB_DRIVER is not set. Check [docker-compos.example.yml](https://github.com/zurdi15/romm/blob/master/docker/docker-compose.example.yml)
 - Platforms and games are now shown by alphabetical order

<br>

# v1.1 (_27-03-2023_)

## Added

 - Game names parentheses are now omitted when searching game in IGDB, allowing game names to have tags.

<br>
 
# v1.0 (_27-03-2023_)
 
## Added
   
- Birth of RomM