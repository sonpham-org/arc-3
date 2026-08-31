"""q786 Backstage Rhythm -- interrupt at a signed continuous-state window after macro routines."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,PULSE,MACRO,POSITIVE,NEGATIVE,WINDOW,INTERRUPT,BAD=9,13,10,14,11,6,8,12,15
LEVELS=[
 {"name":"First Window","seq":(1,)},{"name":"Macro Turn","seq":(1,2,1)},
 {"name":"Chunked Pressure","seq":(3,2,1)},{"name":"Signed Rhythm","seq":(1,1,2,3)},
 {"name":"Long Routine","seq":(3,2,1,2,3)},{"name":"Backstage Rhythm","seq":(1,3,2,3,2,1)}]
def core(s,a,x):
 value,direction,macro,local,interrupted=s
 if a==1:value+=direction;local+=1
 elif a==2:macro+=1;local=0;direction*=-1
 elif a==3:value+=3*direction;local+=3
 elif a==4:
  if (value,direction,macro,local)!=x["goal"]:return None
  interrupted=x["goal"]
 elif a==5:value=0;local=0
 return value,direction,macro,local,interrupted
for x in LEVELS:
 s=(0,1,0,0,None)
 for a in x["seq"]:s=core(s,a,x);assert s is not None
 x["goal"]=(s[0],s[1],s[2],s[3]);x["plan"]=x["seq"]+(4,)
def target(x):
 s=(0,1,0,0,None)
 for a in x["plan"]:s=core(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE
  for i in range(6):f[8+i*6:12+i*6,8:56]=PULSE if i%2==0 else MACRO
  width=min(abs(g.value),12)*3;f[40:44,8:8+width]=POSITIVE if g.value>=0 else NEGATIVE;f[48:52,8:28]=WINDOW;f[48:52,36:56]=POSITIVE if g.direction>0 else NEGATIVE
  if g.interrupted:f[54:59,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q786(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q786",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.value=0;self.direction=1;self.macro=self.local=0;self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=core((self.value,self.direction,self.macro,self.local,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.value,self.direction,self.macro,self.local,self.interrupted=s
  elif a==6:
   if (self.value,self.direction,self.macro,self.local,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
