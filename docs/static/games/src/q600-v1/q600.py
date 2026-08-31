"""q600 Spore Grammar -- compose a message across unequal relay schedules."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,GLASS,GLYPH,GROUP,RELATION,CLOCK,DECODE,BAD=4,8,12,6,2,9,11,13,15
LEVELS=[{"name":"Twin Relay","cycles":(2,2),"group":True},{"name":"Unequal Relay","cycles":(2,3),"group":False},{"name":"Grouped Message","cycles":(3,3),"group":True},{"name":"Sparse Syntax","cycles":(3,4),"group":False},{"name":"Long Relay","cycles":(4,5),"group":True},{"name":"Spore Grammar","cycles":(5,6),"group":True}]
for x in LEVELS:x["plan"]=(1,)*x["cycles"][0]+(2,)*x["cycles"][1]+(3,5)
def advance(s,a,x):
 group,relation,clocks,trace,decoded=s;clocks=list(clocks)
 if a==1:group=(group+1)%4;clocks[0]=(clocks[0]+1)%x["cycles"][0]
 elif a==2:relation=(relation+1)%3;clocks[1]=(clocks[1]+1)%x["cycles"][1]
 elif a==3:
  if tuple(clocks)!=(0,0):return None
  trace=(trace+group+relation+1)%7
 elif a==4:clocks=[(clocks[i]+1)%x["cycles"][i] for i in range(2)]
 elif a==5:
  if not trace:return None
  decoded=(group,relation,tuple(clocks),trace)
 return group,relation,tuple(clocks),trace,decoded
def target(x):
 s=(0,0,(0,0),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GREENHOUSE
  for i in range(3):x=8+i*17;f[8:26,x:x+13]=GLASS+i
  f[11:17,9:13+g.group*8]=GROUP;f[11:17,26:30+g.relation*10]=RELATION;f[11:17,43:47+g.trace*6]=GLYPH
  f[34:38,8:8+g.clocks[0]*8]=CLOCK;f[42:46,8:8+g.clocks[1]*7]=CLOCK+2
  if g.decoded:f[52:57,38:56]=DECODE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q600(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q600",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.group=self.relation=0;self.clocks=(0,0);self.trace=0;self.decoded=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.group,self.relation,self.clocks,self.trace,self.decoded),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.group,self.relation,self.clocks,self.trace,self.decoded=s
  elif a==6:
   if (self.group,self.relation,self.clocks,self.trace,self.decoded)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
