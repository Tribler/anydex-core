import operator
from collections import namedtuple
from functools import cmp_to_key

class MatchPriorityQueue:
    """
    This priority queue keeps track of incoming match message for a specific order.
    """
    _QueueItem = namedtuple("QueueItem", ("retries", "price", "order_id", "other_quantity"))

    def __init__(self, order):
        self.order = order
        self.queue = []

    def __str__(self):
        return ' '.join(map(str, self.queue))

    def is_empty(self):
        return len(self.queue) == 0

    def contains_order(self, order_id):
        return any(queue_item.order_id == order_id for queue_item in self.queue)

    def insert(self, retries, price, order_id, other_quantity):
        self.queue.append(MatchPriorityQueue._QueueItem(retries, price, order_id, other_quantity))

        def cmp_items(queue_item1, queue_item2):
            if queue_item1.retries < queue_item2.retries:
                return -1
            elif queue_item1.retries > queue_item2.retries:
                return 1
            else:
                if self.order.is_ask():
                    # When `self.order` is an ask, upon a smaller price the returned code should result in *1*, not *-1*
                    # like the other case!
                    return 1 if queue_item1.price < queue_item2.price else -1 
                else:
                    return -1 if queue_item1.price < queue_item2.price else 1 

        self.queue.sort(key=cmp_to_key(cmp_items))

    def delete(self):
        return self.queue.pop(0) if self.queue else None
