# Python 2 sample, scanned as text only. Never executed, never imported.
# It exists so the idiom scanner has genuine Python 2 code to detect.
print "starting ledger"
for i in xrange(10):
    print i
data = {"a": 1}
for k, v in data.iteritems():
    print k, v
name = raw_input("name: ")
if data.has_key("a"):
    print unicode(name)
print long(42)
