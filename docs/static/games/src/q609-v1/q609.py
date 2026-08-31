"""q609 Reedbed Grammar -- compose a relay message whose glyphs also alter connectivity."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,GLYPH0,GLYPH1,GROUP,LINK,CODE,COMMIT,BAD=3,10,9,12,14,11,6,13,15
LEVELS=[
 {"name":"Two Glyphs","glyphs":(1,2),"reverse":0},{"name":"Grouped Relay","glyphs":(2,1,2),"reverse":0},
 {"name":"Reversed Marsh","glyphs":(1,2,2),"reverse":1},{"name":"Connected Grammar","glyphs":(2,1,1,2),"reverse":0},
 {"name":"Long Relation","glyphs":(1,2,1,2,2),"reverse":1},{"name":"Reedbed Grammar","glyphs":(2,1,2,2,1,2),"reverse":1}]
def decode(buf,links):return (sum((i+1)*b for i,b in enumerate(buf))+links.bit_count())%4
for x in LEVELS:
 buf=[];links=0
 for a in x["glyphs"]:buf.append(a-1);links^=1<<((len(buf)-1)%4)
 if x["reverse"]:buf.reverse();links=((links<<1)|(links>>3))&15
 x["target"]=decode(buf,links);x["plan"]=x["glyphs"]+(3,)*x["reverse"]+(4,5)
def advance(s,a,x):
 buf,links,code,committed=s;buf=list(buf)
 if a in (1,2):buf.append(a-1);links^=1<<((len(buf)-1)%4)
 elif a==3:buf.reverse();links=((links<<1)|(links>>3))&15
 elif a==4:
  if len(buf)<2:return None
  code=decode(buf,links)
 elif a==5:
  if code!=x["target"]:return None
  committed=(code,links)
 return tuple(buf),links,code,committed
def target(x):
 s=((),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER;f[8:31,8:56]=GROUP
  for i,b in enumerate(g.buf[-6:]):x=10+i*7;f[12:27,x:x+5]=GLYPH1 if b else GLYPH0
  f[33:35,8:28]=LINK
  for i in range(4):f[36+i*4:39+i*4,8:28]=LINK if g.links&(1<<i) else GROUP
  f[38:43,36:56]=CODE+(g.code or 0)
  if g.committed:f[54:59,39:56]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q609(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q609",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buf=();self.links=0;self.code=self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buf,self.links,self.code,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.buf,self.links,self.code,self.committed=s
  elif a==6:
   if (self.buf,self.links,self.code,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
