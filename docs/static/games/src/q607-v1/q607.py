"""q607 Catalyst Grammar -- store a composed code before relay transforms, then execute it hidden."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,GLYPH0,GLYPH1,PIPE,MEMORY,TRANSFORM,PRODUCT,BAD=3,12,9,14,10,6,13,11,15
LEVELS=[
 {"name":"Two Glyphs","glyphs":(1,2),"transforms":0},{"name":"Grouped Glyphs","glyphs":(2,1,2),"transforms":0},
 {"name":"Relay Transform","glyphs":(1,2,2),"transforms":1},{"name":"Stored Grammar","glyphs":(2,1,1,2),"transforms":2},
 {"name":"Long Message","glyphs":(1,2,1,2,2),"transforms":2},{"name":"Catalyst Grammar","glyphs":(2,1,2,2,1,2),"transforms":3}]
for x in LEVELS:x["plan"]=x["glyphs"]+(3,)+(4,)*x["transforms"]+(5,)
def decode(buf):return sum((i+1)*b for i,b in enumerate(buf))%4
def advance(s,a,x):
 buf,pipe,memory,visible,product=s;buf=list(buf)
 if a in (1,2):buf.append(a-1);pipe=(pipe+a)%4
 elif a==3:
  if len(buf)<2:return None
  memory=(decode(buf)+pipe)%4;visible=1
 elif a==4:buf.reverse();pipe=(pipe+1)%4
 elif a==5:
  if memory is None:return None
  visible=0;product=(memory+pipe)%4
 return tuple(buf),pipe,memory,visible,product
def target(x):
 s=((),0,None,1,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REFINERY;f[8:31,8:56]=PIPE
  for i,b in enumerate(g.buf[-6:]):x=10+i*7;f[12:27,x:x+5]=GLYPH1 if b else GLYPH0
  f[34:36,8:56]=TRANSFORM;f[36:40,8:8+g.pipe*11]=TRANSFORM;f[44:48,8:28]=MEMORY
  if g.memory is not None:f[44:49,36:36+g.memory*5+5]=MEMORY
  if g.product is not None:f[54:59,39:56]=PRODUCT+g.product
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q607(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q607",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buf=();self.pipe=0;self.memory=self.product=None;self.visible=1
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buf,self.pipe,self.memory,self.visible,self.product),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.buf,self.pipe,self.memory,self.visible,self.product=s
  elif a==6:
   if (self.buf,self.pipe,self.memory,self.visible,self.product)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
