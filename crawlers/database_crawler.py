import logging
from core.crawler import Crawler
import sqlalchemy
import pandas as pd
import unicodedata

class DatabaseCrawler(Crawler):

    def crawl(self):        
        db_url = self.cfg.database_crawler.db_url
        db_table = self.cfg.database_crawler.db_table
        text_columns = self.cfg.database_crawler.text_columns
        metadata_columns = self.cfg.database_crawler.metadata_columns
        select_condition = self.cfg.database_crawler.get("select_condition", None)
        doc_id_col = self.cfg.database_crawler.get("doc_id_col", None)

        all_columns = text_columns + metadata_columns
        if select_condition:
            query = f'SELECT {",".join(all_columns)} FROM {db_table} WHERE {select_condition}'
        else:
            query = f'SELECT {",".join(all_columns)} FROM {db_table}'

        conn = sqlalchemy.create_engine(db_url).connect()
        df = pd.read_sql_query(sqlalchemy.text(query), conn)
        
        logging.info(f"indexing {len(df)} rows from the database using query: '{query}'")

        def index_df(doc_id, title, df):
            parts = []
            metadatas = []
            for _, row in df.iterrows():
                text = ' - '.join(row[text_columns].tolist())
                parts.append(unicodedata.normalize('NFD', text))
                metadatas.append({column: row[column] for column in metadata_columns})
            logging.info(f"Indexing df for '{doc_id}' with ({len(df)}) rows")
            self.indexer.index_segments(doc_id, parts, metadatas, title=title, doc_metadata = {'source': 'database'})

        if doc_id_col:
            grouped = df.groupby(doc_id_col)
            for name, group in grouped:
                index_df(doc_id=name, title=name, df=group)
        else:
            rows_per_chunk = self.cfg.database_crawler.get("rows_per_chunk", 500)
            for inx in range(0, df.shape[0], rows_per_chunk):
                sub_df = df[inx: inx+rows_per_chunk]
                name = f'rows {inx}-{inx+rows_per_chunk-1}'
                index_df(doc_id=name, title=name, df=sub_df)
        