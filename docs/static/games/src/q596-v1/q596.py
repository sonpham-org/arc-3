"""q596 Palimpsest Grammar -- isolate one causal symbol from a near-miss message."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,GLYPH,GROUP,RELATION,TRACE,DECODE,BAD=0,8,11,6,2,9,4,13,15
LEVELS=[
 {"name":"Correct Relation","required":1,"plan":(2,3,5)},{"name":"Second Relation","required":2,"plan":(2,2,3,5)},
 {"name":"Grouped Difference","required":1,"plan":(1,2,3,5)},{"name":"Overwritten Shelf","required":2,"plan":(1,4,2,2,3,5)},
 {"name":"Composed Correction","required":1,"plan":(4,1,2,4,3,5)},{"name":"Palimpsest Grammar","required":2,"plan":(1,4,2,1,2,3,4,3,5)}]
def advance(s,a,x):
 group,relation,trace,overwrite,decoded=s
 if a==1:group=(group+1)%4
 elif a==2:relation=(relation+1)%3
 elif a==3:trace=(trace+group+relation+overwrite+1)%6
 elif a==4:overwrite=(overwrite+1)%4
 elif a==5:
  if relation!=x["required"]:return None
  decoded=(group,relation,trace,overwrite)
 return group,relation,trace,overwrite,decoded
def target(x):
 s=(0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE
  for i in range(4):f[8+i*9:14+i*9,8:56]=SHELF+i%2
  f[10:15,9:13+g.group*8]=GROUP;f[19:24,9:13+g.relation*11]=RELATION;f[28:33,9:13+g.trace*7]=TRACE
  f[43:47,8:8+g.overwrite*11]=GLYPH;f[49:52,8:56]=BAD
  if g.decoded:f[54:58,38:56]=DECODE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q596(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q596",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.group=self.relation=self.trace=self.overwrite=0;self.decoded=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.group,self.relation,self.trace,self.overwrite,self.decoded),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.group,self.relation,self.trace,self.overwrite,self.decoded=s
  elif a==6:
   if (self.group,self.relation,self.trace,self.overwrite,self.decoded)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
