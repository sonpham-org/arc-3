"""q441 Aurora Lineage -- track crystal ancestry through a visible hysteresis loop."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,CURTAIN,CRYSTAL,TRAIL,CONTROL,SELECT,TARGET,BAD=4,10,15,14,11,9,6,0,8
LEVELS=[{"name":"First Split","ancestor":1,"ops":(1,)},{"name":"Appearance Sweep","ancestor":2,"ops":(3,1,4)},{"name":"Merged Curtain","ancestor":3,"ops":(1,2,3)},{"name":"Hysteresis Trail","ancestor":2,"ops":(3,1,4,2,1)},{"name":"Return Light","ancestor":1,"ops":(1,3,4,2,1,4)},{"name":"Aurora Lineage","ancestor":3,"ops":(3,1,2,4,3,1,2)}]
def advance(s,a):
 tokens,control,direction=s;t=[list(x) for x in tokens]
 if a==1:
  m,c=t.pop(0);t.extend([[m,(c+1+control)%4],[m,(c+2)%4]])
 elif a==2 and len(t)>=2:
  p=t.pop(0);q=t.pop(0);t.insert(0,[p[0]|q[0],(p[1]+q[1])%4])
 elif a==3:
  colors=[x[1] for x in t][1:]+[t[0][1]]
  for x,c in zip(t,colors):x[1]=c
 elif a==4:
  control=(control+direction)%3
  if control in (0,2):direction=-direction
  t.reverse()
 return tuple((x[0],x[1]) for x in t),control,direction
def target(x):
 s=(((1,0),(2,1),(4,2)),0,1)
 for a in x["ops"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=SKY;f[8:16,8:56]=CURTAIN
  for i,(mask,color) in enumerate(g.tokens):px=7+i*12;f[22:31,px:px+9]=CRYSTAL-color%3;f[33:36,px:px+min(mask,7)*2]=TRAIL
  f[44:47,8:8+g.control*14]=CONTROL;f[51:54,8:8+g.selection*13]=SELECT;f[56:59,8:8+x["ancestor"]*13]=TARGET
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q441(ARCBaseGame):
 def __init__(self):self.display=D(self);self.tokens=((1,0),(2,1),(4,2));self.control=self.selection=0;self.direction=1;self.bad=False;self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q441",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.tokens=((1,0),(2,1),(4,2));self.control=self.selection=0;self.direction=1;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.tokens,self.control,self.direction=advance((self.tokens,self.control,self.direction),a)
  elif a==5:self.selection=(self.selection+1)%4
  elif a==6:
   if (self.tokens,self.control,self.direction)==self.target and self.selection==x["ancestor"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
