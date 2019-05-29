from functools import cmp_to_key


class MatchPriorityQueue(object):
    """
    This priority queue keeps track of incoming match message for a specific order.
    """
    def __init__(self, order):
        self.order = order
        self.queue = []

    def __str__(self):
        return ' '.join([str(i) for i in self.queue])

    def is_empty(self):
        return len(self.queue) == []

    def contains_order(self, order_id):
        for _, _, other_order_id in self.queue:
            if other_order_id == order_id:
                return True
        return False

    def insert(self, retries, price, order_id):
        self.queue.append((retries, price, order_id))

        def cmp_items(tup1, tup2):
            if tup1[0] < tup2[0]:
                return -1
            elif tup1[0] > tup2[0]:
                return 1
            else:
                if self.order.is_ask():
                    if tup1[1] < tup2[1]:
                        return 1
                    else:
                        return -1
                else:
                    if tup1[1] < tup2[1]:
                        return -1
                    else:
                        return 1

        self.queue = sorted(self.queue, key=cmp_to_key(cmp_items))

    def delete(self):
        if not self.queue:
            return None

        return self.queue.pop(0)
