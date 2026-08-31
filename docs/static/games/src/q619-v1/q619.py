"""q619 Monsoon Grammar -- compose rain glyphs only at an unequal-clock phase pair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,RAIN0,RAIN1,STORM,CLOCK0,CLOCK1,GROUP,CODE,BAD=3,7,10,11,14,6,12,9,13,15
LEVELS=[
 {"name":"First Storm","glyphs":(1,2),"periods":(2,3),"wait":1},
 {"name":"Delayed Relay","glyphs":(2,1),"periods":(2,3),"wait":2},
 {"name":"Unequal Clocks","glyphs":(1,1,2),"periods":(3,4),"wait":3},
 {"name":"Phase Pair","glyphs":(2,1,2,1),"periods":(3,5),"wait":4},
 {"name":"Long Storm Message","glyphs":(1,2,1,2,2),"periods":(4,5),"wait":6},
 {"name":"Monsoon Grammar","glyphs":(2,1,2,2,1,2),"periods":(4,7),"wait":8}]
def advance(s,a,x):
 buf,p0,p1,groups,code=s;buf=list(buf)
 if a in (1,2):buf.append(a-1)
 elif a==3:p0=(p0+1)%x["periods"][0];p1=(p1+1)%x["periods"][1]
 elif a==4:
  if (p0,p1)!=x["gate"] or len(buf)<2:return None
  kind=(sum((i+1)*v for i,v in enumerate(buf))+p0+2*p1)%5;groups=groups+(kind,);buf=[]
 elif a==5:
  if not groups or buf:return None
  code=(sum(groups)+p0+p1)%6
 return tuple(buf),p0,p1,groups,code
for x in LEVELS:
 x["gate"]=(x["wait"]%x["periods"][0],x["wait"]%x["periods"][1]);x["plan"]=x["glyphs"]+(3,)*x["wait"]+(4,5)
def target(x):
 s=((),0,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i in range(6):x=8+i*9;f[9:15,x:x+6]=RAIN0 if i%2 else RAIN1;f[18:21,x:x+7]=STORM
  for i,v in enumerate(g.buf[-6:]):f[27:38,8+i*9:15+i*9]=RAIN1 if v else RAIN0
  f[43:47,8:8+g.p0*8+6]=CLOCK0;f[49:53,8:8+g.p1*6+6]=CLOCK1
  if g.groups:f[55:59,8:28]=GROUP
  if g.code is not None:f[55:59,43:56]=CODE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q619(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q619",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buf=();self.p0=self.p1=0;self.groups=();self.code=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buf,self.p0,self.p1,self.groups,self.code),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.buf,self.p0,self.p1,self.groups,self.code=s
  elif a==6:
   if (self.buf,self.p0,self.p1,self.groups,self.code)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
