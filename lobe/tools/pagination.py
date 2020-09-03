from math import ceil


class ListPagination:
    def __init__(self, items, page, page_size=20):
        self.page = page
        self.page_size = page_size
        self.num_items = len(items)
        self.total = self.num_items
        self.items = items[
            (page-1)*page_size:min(page*page_size, self.num_items)]

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def pages(self):
        # get number of pages
        return ceil(self.num_items/self.page_size)

    @property
    def next_num(self):
        return self.page + 1

    @property
    def prev_num(self):
        return self.page - 1