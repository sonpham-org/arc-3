"""q606 Backstage Grammar -- compose signed glyph pressure through a directional relay."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,GLYPH0,GLYPH1,GROUP,POSITIVE,NEGATIVE,COMMIT,BAD=3,13,10,14,6,11,9,12,15
LEVELS=[
 {"name":"Two Glyphs","glyphs":(1,2),"reverse":0},{"name":"Grouped Pressure","glyphs":(2,1,2),"reverse":0},
 {"name":"Reversed Relay","glyphs":(1,2,2),"reverse":1},{"name":"Signed Grammar","glyphs":(2,1,1,2),"reverse":0},
 {"name":"Long Message","glyphs":(1,2,1,2,2),"reverse":1},{"name":"Backstage Grammar","glyphs":(2,1,2,2,1,2),"reverse":1}]
def decode(buf,value):return (sum((i+1)*v for i,v in enumerate(buf))+abs(value)+int(value<0))%4
for x in LEVELS:
 value=sum(1 if a==1 else -2 for a in x["glyphs"]);buf=[a-1 for a in x["glyphs"]]
 if x["reverse"]:buf.reverse();value=-value
 x["target"]=decode(buf,value);x["plan"]=x["glyphs"]+(3,)*x["reverse"]+(4,5)
def advance(s,a,x):
 buf,value,code,committed=s;buf=list(buf)
 if a in (1,2):buf.append(a-1);value+=1 if a==1 else -2
 elif a==3:buf.reverse();value=-value
 elif a==4:
  if len(buf)<2:return None
  code=decode(buf,value)
 elif a==5:
  if code!=x["target"]:return None
  committed=(code,value)
 return tuple(buf),value,code,committed
def target(x):
 s=((),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE;f[8:31,8:56]=GROUP
  f[34:37,8:28]=GLYPH0;f[34:37,36:56]=GLYPH1
  for i,b in enumerate(g.buf[-6:]):x=10+i*7;f[12:27,x:x+5]=GLYPH1 if b else GLYPH0
  width=min(abs(g.value),12)*3;f[37:42,8:8+width]=POSITIVE if g.value>=0 else NEGATIVE
  if g.committed:f[54:59,39:56]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q606(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q606",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buf=();self.value=0;self.code=self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buf,self.value,self.code,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.buf,self.value,self.code,self.committed=s
  elif a==6:
   if (self.buf,self.value,self.code,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
