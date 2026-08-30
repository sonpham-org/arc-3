"""q345 Vivarium Survey -- allocate temperature samples while partner favor changes policy."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GLASS,HABITAT,FAUNA,SAMPLE,SELECT,FAVOR,POLICY,BAD=14,10,0,6,15,12,11,9,8
LEVELS=[{"name":"One Stratum","samples":(1,),"policy":1,"budget":2},{"name":"Partner View","samples":(2,4,1),"policy":2,"budget":3},{"name":"Evidence Union","samples":(1,3,4,2),"policy":3,"budget":4},{"name":"Fair Help","samples":(2,4,3,1,5),"policy":1,"budget":4},{"name":"Reciprocal Route","samples":(3,1,4,2,5,3),"policy":2,"budget":5},{"name":"Vivarium Survey","samples":(1,4,3,2,5,4,1),"policy":3,"budget":6}]
def advance(s,a):
 selected,evidence,favor,policy,cost=s;evidence=list(evidence)
 if a in (1,2,3):item=(selected,a,(selected+a+favor)%4);cost+=2 if item in evidence else 1;evidence.append(item)
 elif a==4:selected=1-selected
 elif a==5:favor=(favor+selected+1)%4;policy=(policy+favor+1)%4
 return selected,tuple(evidence),favor,policy,cost
def target(x):
 s=(0,(),0,0,0)
 for a in x["samples"]:s=advance(s,a)
 for _ in range(x["policy"]):s=advance(s,5)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GLASS
  for i in range(2):y=9+i*23;f[y:y+19,9:55]=HABITAT;f[y+4:y+11,14:24]=FAUNA
  f[7:10,9+g.selected*27:30+g.selected*27]=SELECT
  for i,(_,_,v) in enumerate(g.evidence[-8:]):f[42+i*2:44+i*2,7:7+v*12]=SAMPLE
  f[55:58,7:7+g.favor*12]=FAVOR;f[59:61,7:7+g.policy*12]=POLICY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q345(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.selected=0;self.evidence=();self.favor=self.policy=self.cost=0;self.bad=False;self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q345",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.selected=0;self.evidence=();self.favor=self.policy=self.cost=0;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   self.selected,self.evidence,self.favor,self.policy,self.cost=advance((self.selected,self.evidence,self.favor,self.policy,self.cost),a)
   if self.cost>x["budget"]:self.bad=True;self.lose()
  elif a==6:
   if (self.selected,self.evidence,self.favor,self.policy,self.cost)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
