"""q679 Monsoon Analogy -- transfer a storm relation at unequal phase pairs."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,SOURCE,TARGET,RAIN,CLOUD,PHASE,GOAL,BAD=8,11,4,12,14,10,6,13,15
LEVELS=[{"name":"Storm Relation","seq":(4,)},{"name":"Fast Cycle","seq":(1,4)},{"name":"Slow Cycle","seq":(2,1,4)},{"name":"Changed Surface","seq":(3,1,2,4)},{"name":"Phase Transfer","seq":(1,3,2,1,4)},{"name":"Monsoon Analogy","seq":(2,1,3,2,1,3,4)}]
def advance(s,a):
 source,target,fast,slow,samples,mapped,locked=s;x=list(source);y=list(target)
 if a==1:fast=(fast+1)%4;slow=(slow+int(fast==0))%5;x[0]=(x[0]+1+fast)%7;y[1]=(y[1]+2+slow)%7
 elif a==2:fast=(fast+2)%4;slow=(slow+1)%5;x[1]=(x[1]+slow)%7;y[0]=(y[0]+fast)%7
 elif a==3:samples=samples+((fast,slow,(x[1]-x[0])%7,(y[1]-y[0])%7),)
 elif a==4:mapped=((x[1]-x[0])%7,(y[1]-y[0])%7,fast,slow,samples[-2:])
 elif a==5:locked=(mapped,tuple(x),tuple(y),fast,slow,samples[-2:])
 return tuple(x),tuple(y),fast,slow,samples,mapped,locked
for x in LEVELS:
 s=((0,3),(1,5),0,0,(),None,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN;f[8:31,7:29]=SOURCE;f[8:31,35:57]=TARGET
  for side,vals in enumerate((g.source,g.target)):
   ox=9+side*28
   for i,v in enumerate(vals):f[11+i*11:19+i*11,ox:ox+16]=CLOUD;f[14+i*11:18+i*11,ox+2:ox+4+v*2]=RAIN if side else PHASE
  for i,(a,b,_,_) in enumerate(g.samples[-3:]):x=8+i*15;f[37:43,x:x+11]=PHASE;f[44:47,x:x+2+a*2]=RAIN;f[48:50,x:x+2+b*2]=CLOUD
  f[52:55,8:8+g.fast*11+8]=RAIN;f[56:59,8:8+g.slow*9+7]=CLOUD
  if g.locked:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q679(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q679",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=(0,3);self.target=(1,5);self.fast=self.slow=0;self.samples=();self.mapped=self.locked=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.source,self.target,self.fast,self.slow,self.samples,self.mapped,self.locked=advance((self.source,self.target,self.fast,self.slow,self.samples,self.mapped,self.locked),a)
  elif a==6:
   if (self.source,self.target,self.fast,self.slow,self.samples,self.mapped,self.locked)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
