class AppException(Exception):
	def __init__(self, *args, **kargs):
		if kargs.get('meta', None) is not None:
			meta = kargs['meta']
			del kargs['meta']
			self.meta = meta
		Exception.__init__(self, *args, **kargs)
