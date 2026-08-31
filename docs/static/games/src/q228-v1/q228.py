"""q228 Escapement Veil -- schedule attention and use one fault-separating intervention."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,FOCUS,PHASE,DIAG,GOAL,BAD=0,10,9,14,6,11,4,7,15
LEVELS=[{"name":"First Weight","fault":1,"plan":(1,4)},{"name":"Hidden Gear","fault":2,"plan":(2,1,4)},{"name":"Fault Sample","fault":3,"plan":(3,4,5,1)},{"name":"Coupled Escapement","fault":2,"plan":(1,4,2,5,3)},{"name":"Diagnostic Return","fault":3,"plan":(2,5,3,4,1,5)},{"name":"Escapement Veil","fault":1,"plan":(3,4,1,5,2,4,3,5)}]
def advance(s,a,x):
 weights,focus,phase,diagnostic=s;weights=list(weights)
 if a in (1,2,3):
  focus=a-1
  for i in range(3):
   if i!=focus:weights[i]=(weights[i]+phase+x["fault"]+i)%5
 elif a==4:diagnostic=(x["fault"],weights[focus],phase);weights[focus]=(weights[focus]+x["fault"]+phase)%5;phase=(phase+1)%4
 elif a==5:
  if diagnostic:weights=[(v+diagnostic[0]+i)%5 for i,v in enumerate(weights)]
 return tuple(weights),focus,phase,diagnostic
def target(x):
 s=((0,2,4),0,0,None)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i,v in enumerate(g.weights):x=8+i*18;f[9:38,x:x+14]=GEAR;f[14+v*5:21+v*5,x+4:x+10]=WEIGHT-i
  f[7:10,8+g.focus*18:22+g.focus*18]=FOCUS;f[43:46,8:11+g.phase*11]=PHASE;f[50:53,8:20]=DIAG if g.diagnostic else GEAR;f[56:59,48:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q228(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q228",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.weights=(0,2,4);self.focus=self.phase=0;self.diagnostic=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.weights,self.focus,self.phase,self.diagnostic=advance((self.weights,self.focus,self.phase,self.diagnostic),a,x)
  elif a==6:
   if (self.weights,self.focus,self.phase,self.diagnostic)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
