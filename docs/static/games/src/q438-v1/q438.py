"""q438 Escapement Revision -- recalibrate a worn gear law with one fault intervention."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,WEAR,PROBE,OUTCOME,RULE,BAD=4,3,1,14,12,10,15,11,8
LEVELS=[{"name":"Old Gear","boundary":3,"mode":1,"fault":1,"plan":(1,2,4)},{"name":"Wear Signal","boundary":2,"mode":2,"fault":2,"plan":(2,1,5,4)},{"name":"Inverted Weight","boundary":2,"mode":3,"fault":3,"plan":(3,2,4,1)},{"name":"Fault Contrast","boundary":3,"mode":2,"fault":2,"plan":(1,4,5,2,3)},{"name":"Sparse Recalibration","boundary":2,"mode":1,"fault":1,"plan":(2,3,4,1,5,2)},{"name":"Escapement Revision","boundary":3,"mode":3,"fault":3,"plan":(3,1,5,2,4,3,1)}]
def advance(s,a,x):
 weights,wear,probe,outcome,delay=s;weights=list(weights)
 if a in (1,2,3):
  i=a-1;rule=1 if wear<x["boundary"] else x["mode"]
  if rule==1:weights[i]=(weights[i]+a)%4
  elif rule==2:weights[i]=3-weights[i]
  else:delay=(delay+a+i)%4
  wear+=1
 elif a==4:probe=(probe+1)%4;outcome=(x["fault"]*probe+sum(weights))%4
 elif a==5:weights=[(v+delay)%4 for v in weights];delay=0
 return tuple(weights),wear,probe,outcome,delay
def target(x):
 s=((0,1,2),0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i,v in enumerate(g.weights):x=8+i*18;f[10:31,x:x+14]=GEAR;f[16+v*3:22+v*3,x+4:x+10]=WEIGHT
  f[37:40,8:14]=WEAR;f[37:40,16:16+min(g.wear,8)*6]=WEAR
  f[43:46,8:14]=PROBE;f[43:46,16:16+g.probe*10]=PROBE
  f[48:51,8:14]=OUTCOME;f[48:51,16:16+g.outcome*10]=OUTCOME
  f[54:57,8:14]=RULE;f[54:57,16:16+g.delay*10]=RULE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q438(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.weights=(0,1,2);self.wear=self.probe=self.outcome=self.delay=0;self.bad=False;self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q438",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.weights=(0,1,2);self.wear=self.probe=self.outcome=self.delay=0;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.weights,self.wear,self.probe,self.outcome,self.delay=advance((self.weights,self.wear,self.probe,self.outcome,self.delay),a,x)
  elif a==6:
   if (self.weights,self.wear,self.probe,self.outcome,self.delay)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
