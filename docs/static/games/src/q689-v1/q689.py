"""q689 Strata Evidence -- stop probing when persistent fault evidence fixes the quarry decision."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,ORE,FAULT,PROBE,EVIDENCE,MARGIN,GOAL,BAD=6,11,14,10,8,9,12,13,15
LEVELS=[
 {"name":"One Probe","seq":(1,)},{"name":"Reversible Fault","seq":(2,1)},
 {"name":"Persistent Reading","seq":(3,1,2)},{"name":"Bounded Margin","seq":(1,3,2,1)},
 {"name":"Costly Diagnosis","seq":(2,3,1,2,3,1)},
 {"name":"Strata Evidence","seq":(1,2,3,1,3,2,1,2,3)}]
def advance(s,a):
 physical,fault,evidence,margin,cost,stopped=s
 if a==1:physical=(physical+1+fault)%5;margin+=2+physical;evidence=evidence+((physical,fault,1),);cost+=1
 elif a==2:physical=(2*physical+1)%5;margin-=1+fault;evidence=evidence+((physical,fault,-1),);cost+=2
 elif a==3:fault=(fault+1)%4;physical=0;margin+=fault-1
 elif a==4:physical=0;cost+=1
 elif a==5:stopped=(physical,fault,evidence[-4:],margin,cost)
 return physical,fault,evidence,margin,cost,stopped
for x in LEVELS:
 s=(0,0,(),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=QUARRY
  for i in range(5):x=8+i*10;f[8:29,x:x+7]=FAULT;f[23-i*3:28,x+2:x+6]=ORE if i==g.physical else PROBE
  for i,(p,h,sign) in enumerate(g.evidence[-5:]):x=8+i*10;f[35:41,x:x+7]=EVIDENCE if sign>0 else PROBE;f[42:45,x:x+2+h]=FAULT
  center=31;lo=max(5,min(center,center+g.margin));hi=min(58,max(center,center+g.margin));f[49:54,lo:hi+1]=MARGIN
  if g.stopped:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q689(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q689",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.physical=self.fault=self.margin=self.cost=0;self.evidence=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.physical,self.fault,self.evidence,self.margin,self.cost,self.stopped=advance((self.physical,self.fault,self.evidence,self.margin,self.cost,self.stopped),a)
  elif a==6:
   if (self.physical,self.fault,self.evidence,self.margin,self.cost,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
