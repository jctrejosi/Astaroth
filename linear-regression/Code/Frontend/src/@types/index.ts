export type TableCell = string | number | null;

export type TableRow = TableCell[];

export type Pagination = {
  page: number;
  page_size: number;

  total_rows: number;
  total_pages: number;

  has_next: boolean;
  has_prev: boolean;
};

export type DatasetMeta = {
  memory_mb: number;
  total_columns: number;
};

export type TableFile = {
  ok: boolean;

  file_id: string;

  columns: string[];

  data: TableRow[];

  pagination: Pagination;

  meta: DatasetMeta;
};
