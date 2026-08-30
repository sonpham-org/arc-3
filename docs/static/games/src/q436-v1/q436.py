"""q436 Crossing Revision -- recalibrate a worn ferry through controller-specific marks."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,BANK,FERRY,PASSENGER,WEAR,CONTROL,MARK,BAD=9,10,12,0,15,11,14,6,8
LEVELS=[
 {"name":"Old Crossing","boundary":3,"mode":1,"plan":(1,4)},
 {"name":"Visible Wear","boundary":2,"mode":2,"plan":(2,1,5,4)},
 {"name":"Inverted Dock","boundary":2,"mode":3,"plan":(3,2,4,1)},
 {"name":"Disjoint Attributes","boundary":3,"mode":2,"plan":(1,4,5,2,3)},
 {"name":"Sparse Recalibration","boundary":2,"mode":1,"plan":(2,4,1,5,3,4)},
 {"name":"Crossing Revision","boundary":3,"mode":3,"plan":(3,1,4,5,2,4,1,3)}]
def advance(s,a,x):
 passengers,wear,controller,marks,dock=s;passengers=list(passengers);marks=list(marks)
 if a in (1,2,3):
  i=a-1;rule=1 if wear<x["boundary"] else x["mode"]
  passengers[i]=(passengers[i]+rule+i+controller)%4;wear+=1;dock=(dock+rule+i)%3
 elif a==4:marks[controller]=(sum(passengers)+dock+controller)%8
 elif a==5:controller=1-controller;dock=(dock+1)%3
 return tuple(passengers),wear,controller,tuple(marks),dock
def target(x):
 s=((0,1,2),0,0,(0,0),0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[8:56,3:61]=RIVER;f[4:10,:]=BANK;f[54:60,:]=BANK
  x=9+g.dock*16;f[29:39,x:x+20]=FERRY
  for i,v in enumerate(g.passengers):f[13+i*11:20+i*11,8+v*12:16+v*12]=PASSENGER
  f[7:10,8:8+min(g.wear,8)*6]=WEAR;f[58:61,8:8+g.controller*22]=CONTROL
  for i,v in enumerate(g.marks):f[23+i*22:26+i*22,45:45+v*2]=MARK
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q436(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.target=target(LEVELS[0]);self._reset()
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q436",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.passengers=(0,1,2);self.wear=0;self.controller=0;self.marks=(0,0);self.dock=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.passengers,self.wear,self.controller,self.marks,self.dock=advance((self.passengers,self.wear,self.controller,self.marks,self.dock),a,x)
  elif a==6:
   if (self.passengers,self.wear,self.controller,self.marks,self.dock)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
