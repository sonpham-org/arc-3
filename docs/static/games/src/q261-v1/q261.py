"""q261 Aurora Probe -- distinguish causal rays while curtain control follows hysteresis."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,CURTAIN,MOTE,RAY,EVIDENCE,CONTROL,CHOICE,BAD=9,10,15,14,12,11,6,0,8
LEVELS=[{"name":"Direct Ray","model":1,"tests":(1,)},{"name":"Shared Curtain","model":2,"tests":(2,1)},{"name":"Coincident Mote","model":3,"tests":(1,3,2)},{"name":"Hysteretic Probe","model":2,"tests":(3,4,1,2)},{"name":"Return Sweep","model":3,"tests":(2,1,4,3,2)},{"name":"Aurora Probe","model":1,"tests":(1,4,3,2,4,1)}]
def result(model,a,control,direction):return (model*a+control+direction)%4
def required(x):
 out=[];control=0;direction=1
 for a in x["tests"]:
  if a==4:
   control=(control+direction)%3
   if control in (0,2):direction=-direction
  else:out.append((a,control,result(x["model"],a,control,direction)))
 return tuple(out),control,direction
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY;f[9:19,8:56]=CURTAIN
  for i in range(3):x=10+i*17;f[25:34,x:x+9]=MOTE;f[34:42,x+3:x+6]=RAY
  for i,(_,_,v) in enumerate(g.evidence[-8:]):f[44+i*2:46+i*2,7:7+v*12]=EVIDENCE
  f[55:58,8:8+g.control*14]=CONTROL;f[59:61,8:8+g.choice*13]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q261(ARCBaseGame):
 def __init__(self):self.display=D(self);self.evidence=[];self.control=self.choice=0;self.direction=1;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q261",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.evidence=[];self.control=self.choice=0;self.direction=1;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.evidence.append((a,self.control,result(x["model"],a,self.control,self.direction)))
  elif a==4:
   self.control=(self.control+self.direction)%3
   if self.control in (0,2):self.direction=-self.direction
  elif a==5:self.choice=(self.choice+1)%4
  elif a==6:
   ev,c,d=required(x)
   if tuple(self.evidence)==ev and self.control==c and self.direction==d and self.choice==x["model"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
