"""q343 Impeller Survey -- buy only the wake samples that can change a route decision."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,ROTOR,BLADE,SAMPLE,SELECT,ROUTE,COST,BAD=1,3,4,9,10,12,14,11,8
LEVELS=[
 {"name":"One Wake","samples":(1,),"policy":1,"budget":2,"wake":(1,2,3)},
 {"name":"Counter Rotation","samples":(2,4,1),"policy":2,"budget":3,"wake":(2,0,3)},
 {"name":"Evidence Union","samples":(1,3,4,2),"policy":3,"budget":4,"wake":(3,1,0)},
 {"name":"Bounded Slices","samples":(2,4,3,1),"policy":1,"budget":4,"wake":(1,3,2)},
 {"name":"Costly Redundancy","samples":(3,1,4,2,3),"policy":2,"budget":5,"wake":(2,3,1)},
 {"name":"Impeller Survey","samples":(1,4,3,2,4,1),"policy":3,"budget":6,"wake":(3,2,1)}]
def required(x):
 selected=0;out=[]
 for a in x["samples"]:
  if a==4:selected=1-selected
  else:out.append((selected,a,(x["wake"][a-1]+selected*2)%4))
 return tuple(out)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER
  for i in range(2):
   x=11+i*30;f[12:38,x:x+22]=ROTOR;f[18:32,x+8:x+14]=BLADE
   if i==g.selected:f[8:12,x:x+22]=SELECT
  for i,(_,_,v) in enumerate(g.evidence[-8:]):f[42+i*2:44+i*2,7:7+v*12]=SAMPLE
  f[55:58,7:7+g.policy*13]=ROUTE;f[59:61,7:7+g.spent*7]=COST
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q343(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.evidence=[];self.selected=self.spent=self.policy=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q343",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.evidence=[];self.selected=self.spent=self.policy=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   item=(self.selected,a,(x["wake"][a-1]+self.selected*2)%4);self.spent+=2 if item in self.evidence else 1;self.evidence.append(item)
   if self.spent>x["budget"]:self.bad=True;self.lose()
  elif a==4:self.selected=1-self.selected
  elif a==5:self.policy=(self.policy+1)%4
  elif a==6:
   if tuple(self.evidence)==required(x) and self.spent<=x["budget"] and self.policy==x["policy"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
