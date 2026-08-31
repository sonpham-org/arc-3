"""q321 Aurora Survey -- allocate finite curtain observations under hysteresis."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,LENS,CURTAIN,MOTE,SAMPLE,CONTROL,POLICY,BAD=10,9,15,14,12,11,6,0,8
LEVELS=[{"name":"One Lens","samples":(1,),"policy":1,"budget":1},{"name":"Second Curtain","samples":(2,4,1),"policy":2,"budget":2},{"name":"Evidence Union","samples":(1,3,4,2),"policy":3,"budget":3},{"name":"Hysteresis View","samples":(2,4,3,1),"policy":1,"budget":3},{"name":"Return Cost","samples":(3,1,4,2,3),"policy":2,"budget":4},{"name":"Aurora Survey","samples":(1,4,3,2,4,1),"policy":3,"budget":4}]
def advance(s,a):
 control,direction,evidence,policy,cost=s;evidence=list(evidence)
 if a in (1,2,3):item=(control,a,(control+a+direction)%4);cost+=2 if item in evidence else 1;evidence.append(item)
 elif a==4:
  control=(control+direction)%3
  if control in (0,2):direction=-direction
 elif a==5:policy=(policy+1)%4
 return control,direction,tuple(evidence),policy,cost
def target(x):
 s=(0,1,(),0,0)
 for a in x["samples"]:s=advance(s,a)
 for _ in range(x["policy"]):s=advance(s,5)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY;f[9:18,8:56]=CURTAIN
  for i in range(3):x=10+i*17;f[23:34,x:x+10]=LENS;f[27:31,x+3:x+7]=MOTE
  for i,(_,_,v) in enumerate(g.evidence[-8:]):f[39+i*2:41+i*2,7:7+v*12]=SAMPLE
  f[54:57,8:8+g.control*14]=CONTROL;f[58:60,8:8+g.policy*13]=POLICY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q321(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q321",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.control=0;self.direction=1;self.evidence=();self.policy=self.cost=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   self.control,self.direction,self.evidence,self.policy,self.cost=advance((self.control,self.direction,self.evidence,self.policy,self.cost),a)
   if self.cost>x["budget"]:self.bad=True;self.lose()
  elif a==6:
   if (self.control,self.direction,self.evidence,self.policy,self.cost)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
