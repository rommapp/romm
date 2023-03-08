import os
import sys
from dataclasses import asdict

from fastapi import HTTPException
import mariadb as db

from config.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWD
from logger.logger import log


class DBHandler:
   
    def __init__(self) -> None:
        try:
            self.conn = db.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWD,
                autocommit=True
            )
        except db.Error as e:
            log.error(f"error connecting to the database: {e}")
            sys.exit(1)
        self.DATABASE: str = 'romm'
        self.PLATFORM_TABLE: str = 'platform'
        self.ROM_TABLE: str = 'rom'
        self.cur = self.conn.cursor()


    def create_platform_table(self, 
                              igdb_id: str, sgdb_id: str,
                              slug: str, name: str,
                              path_logo: str) -> None:
        try:
            self.cur.execute(f"""
            create table if not exists {self.DATABASE}.{self.PLATFORM_TABLE}
                ({igdb_id} varchar(20), {sgdb_id} varchar(20),
                {slug} varchar(50), {name} varchar(100),
                {path_logo} varchar(500))
            """)
            log.info(f"{self.DATABASE}.{self.PLATFORM_TABLE} table created")
        except Exception as e:
            log.error(f"{self.DATABASE}.{self.PLATFORM_TABLE} table can't be created: {e}")
            raise HTTPException(status_code=500, detail=f"Can't create platform table. {e}")
        try:
            self.cur.execute(f"truncate {self.DATABASE}.{self.PLATFORM_TABLE}")
            log.info(f"{self.DATABASE}.{self.PLATFORM_TABLE} table truncated")
        except Exception as e:
            log.error(f"{self.DATABASE}.{self.PLATFORM_TABLE} table can't be truncated: {e}")
            raise HTTPException(status_code=500, detail=f"Can't truncate platform table. {e}")

    
    def create_rom_table(self, 
                         igdb_id: str, sgdb_id: str,
                         platform_igdb_id: str, platform_sgdb_id: str,
                         filename: str, name: str,
                         path_cover: str) -> None:
        try:
            self.cur.execute(f"""
            create table if not exists {self.DATABASE}.{self.ROM_TABLE}
                ({igdb_id} varchar(20), {sgdb_id} varchar(20),
                {platform_igdb_id} varchar(20), {platform_sgdb_id} varchar(20),
                {filename} varchar(200), {name} varchar(100),
                {path_cover} varchar(500))
            """)
            log.info(f"{self.DATABASE}.{self.ROM_TABLE} table created")
        except Exception as e:
            log.error(f"{self.DATABASE}.{self.ROM_TABLE} table can't be created: {e}")
            raise HTTPException(status_code=500, detail=f"Can't create rom table. {e}")
        try:
            self.cur.execute(f"truncate {self.DATABASE}.{self.ROM_TABLE}")
            log.info(f"{self.DATABASE}.{self.ROM_TABLE} table truncated")
        except Exception as e:
            log.error(f"{self.DATABASE}.{self.ROM_TABLE} table can't be truncated: {e}")
            raise HTTPException(status_code=500, detail=f"Can't truncate rom table. {e}")


    def write_platforms(self, platforms: list) -> None:
        values: list = [{k: str(v) for k, v in asdict(p).items()} for p in platforms]
        try:
            self.cur.executemany(f"insert into {self.DATABASE}.{self.PLATFORM_TABLE} (igdb_id, sgdb_id, slug, name, path_logo) \
                                 values (%(igdb_id)s, %(sgdb_id)s, %(slug)s, %(name)s, %(path_logo)s)", values)
            log.info(f"{self.DATABASE}.{self.PLATFORM_TABLE} table populated")
        except Exception as e:
            log.error(f"{self.DATABASE}.{self.PLATFORM_TABLE} can't be populated: {e}")
            raise HTTPException(status_code=500, detail=f"Can't write in platform table. {e}")


    def get_platforms(self) -> list:
        try:
            self.cur.execute(f"select igdb_id, sgdb_id, slug, name, path_logo from {self.DATABASE}.{self.PLATFORM_TABLE}")
            log.info(f"platforms details fetch from {self.DATABASE}.{self.PLATFORM_TABLE}")
        except Exception as e:
            log.error(f"platforms details can't be fetch from {self.DATABASE}.{self.PLATFORM_TABLE}")
            raise HTTPException(status_code=500, detail=f"Can't read platform table. {e}")
        return self.cur

    
    def get_roms(self, platform_id: int) -> list:
        try:
            self.cur.execute(f"select igdb_id, sgdb_id, platform_igdb_id, platform_sgdb_id, filename, name, path_cover from {self.DATABASE}.{self.ROM_TABLE} where platform_id = {platform_id}")
            log.info(f"platforms details fetch from {self.DATABASE}.{self.ROM_TABLE}")
        except Exception as e:
            log.error(f"platforms details can't be fetch from {self.DATABASE}.{self.ROM_TABLE}")
            raise HTTPException(status_code=500, detail=f"Can't read rom table. {e}")
        return self.cur


    def close_conn(self) -> None:
        log.info("closing database connection")
        self.conn.close()
