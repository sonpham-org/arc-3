"""q611 Pollen Grammar -- compose grouped messages through a wear-complemented relay."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,GLYPH0,GLYPH1,GROUP,WEAR,RULE,COMMIT,BAD=2,14,9,12,10,13,6,11,15
LEVELS=[
 {"name":"Two Glyphs","glyphs":(1,2),"wear":5,"reverse":0},{"name":"Grouped Bloom","glyphs":(2,1,2),"wear":5,"reverse":0},
 {"name":"Reversed Relay","glyphs":(1,2,2),"wear":6,"reverse":1},{"name":"Worn Grammar","glyphs":(2,1,1,2),"wear":3,"reverse":0},
 {"name":"Complemented Group","glyphs":(1,2,1,2,2),"wear":4,"reverse":1},{"name":"Pollen Grammar","glyphs":(2,1,2,2,1,2),"wear":5,"reverse":1}]
def decoded(buf,rule):
 v=sum((i+1)*b for i,b in enumerate(buf))%4
 return 3-v if rule else v
for x in LEVELS:
 rule=int(len(x["glyphs"])>=x["wear"]);buf=tuple(a-1 for a in x["glyphs"]);buf=buf[::-1] if x["reverse"] else buf;x["target"]=decoded(buf,rule);x["plan"]=x["glyphs"]+(3,)*x["reverse"]+(4,5)
def advance(s,a,x):
 buf,wear,rule,code,committed=s;buf=list(buf)
 if a in (1,2):
  buf.append(a-1);wear+=1
  if wear==x["wear"]:rule^=1
 elif a==3:buf.reverse()
 elif a==4:
  if len(buf)<2:return None
  code=decoded(buf,rule)
 elif a==5:
  if code!=x["target"]:return None
  committed=code
 return tuple(buf),wear,rule,code,committed
def target(x):
 s=((),0,0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MEADOW;f[8:31,8:56]=GROUP
  for i,b in enumerate(g.buf[-6:]):x=10+i*7;f[12:27,x:x+5]=GLYPH1 if b else GLYPH0
  f[36:40,8:8+min(g.wear,6)*8]=WEAR;f[44:49,8:28]=RULE+g.rule;f[52:57,36:56]=GLYPH0+(g.code or 0)
  if g.committed is not None:f[57:60,39:56]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q611(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q611",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buf=();self.wear=self.rule=0;self.code=self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buf,self.wear,self.rule,self.code,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.buf,self.wear,self.rule,self.code,self.committed=s
  elif a==6:
   if (self.buf,self.wear,self.rule,self.code,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
