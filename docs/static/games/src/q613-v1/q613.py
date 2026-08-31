"""q613 Impeller Grammar -- compose blade glyphs through sampled counter-rotating relays."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,GLYPH0,GLYPH1,GLYPH2,RELAY,WAKE,SAMPLE,COST,CODE,BAD=3,4,10,11,12,14,6,7,5,13,15
LEVELS=[
 {"name":"First Relay","seq":(1,2,3,4)},{"name":"Reverse Pair","seq":(2,1,3,4)},
 {"name":"Two Groups","seq":(1,1,3,4,2,2,3,4)},{"name":"Shifted Grammar","seq":(1,2,3,4,2,1,3,4)},
 {"name":"Costed Message","seq":(1,1,3,4,1,1,3,4,2,2,3,4)},
 {"name":"Impeller Grammar","seq":(2,1,3,4,1,2,3,4,2,2,3,4)}]
def advance(s,a):
 buf,wake,groups,samples,cost,code=s;buf=list(buf)
 if a in (1,2):buf.append(a-1)
 elif a==3:
  if len(buf)<2:return None
  left,right=buf[-2:];kind=(left+2*right+wake)%3;buf=buf[:-2];groups=groups+(kind,);wake=(wake+1+kind)%3
 elif a==4:
  if not groups:return None
  costly=len(samples)>=2 and samples[-1]==samples[-2];samples=samples+(groups[-1],);cost+=2 if costly else 1
 elif a==5:
  if not groups or buf or not samples:return None
  code=(sum((i+1)*v for i,v in enumerate(groups))+wake+cost)%5
 return tuple(buf),wake,groups,samples,cost,code
for x in LEVELS:
 s=((),0,(),(),0,None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=((),0,(),(),0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;cols=(GLYPH0,GLYPH1,GLYPH2)
  for i in range(6):x=8+i*9;f[9:14,x:x+6]=cols[(i+g.wake)%3];f[18:21,x:x+7]=RELAY
  for i,v in enumerate(g.buf[-6:]):f[27:38,8+i*9:15+i*9]=cols[v]
  for i,v in enumerate(g.groups[-5:]):f[43:48,8+i*10:15+i*10]=cols[v]
  f[51:55,8:8+g.wake*15+10]=WAKE;f[56:60,8:8+min(g.cost,9)*5]=COST
  if g.code is not None:f[55:59,43:56]=CODE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q613(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q613",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buf=();self.wake=0;self.groups=self.samples=();self.cost=0;self.code=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buf,self.wake,self.groups,self.samples,self.cost,self.code),a)
   if s is None:self.bad=True;self.lose()
   else:self.buf,self.wake,self.groups,self.samples,self.cost,self.code=s
  elif a==6:
   if (self.buf,self.wake,self.groups,self.samples,self.cost,self.code)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
