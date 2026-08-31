"""q231 Aurora Pact -- infer an offer convention under visible hysteresis."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,CURTAIN,MOTE,OFFER,RESPONSE,CONTROL,CHOICE,BAD=6,10,15,14,12,11,9,0,8
LEVELS=[{"name":"Fair Light","rule":1,"offers":(1,)},{"name":"Recent Curtain","rule":2,"offers":(2,1)},{"name":"Reciprocal Mote","rule":3,"offers":(1,3,2)},{"name":"Hysteresis Loop","rule":2,"offers":(3,4,1,2)},{"name":"Return Control","rule":3,"offers":(2,1,4,3,2)},{"name":"Aurora Pact","rule":1,"offers":(1,4,3,2,4,1)}]
def response(rule,a,last,control,direction):return (rule+a+last+control+direction)%4
def expected(x):
 out=[];last=control=0;direction=1
 for a in x["offers"]:
  if a==4:
   old=control;control=(control+direction)%3
   if control in (0,2):direction=-direction
   out.append((4,control,direction));last=old
  else:out.append((a,response(x["rule"],a,last,control,direction)));last=a
 return tuple(out)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY
  for i in range(3):x=9+i*18;f[9:39,x:x+13]=CURTAIN;f[15+i*6:22+i*6,x+4:x+10]=MOTE
  for i,v in enumerate(g.evidence[-8:]):f[42+i*2:44+i*2,7:7+(v[1]%4)*12]=RESPONSE
  f[54:57,8:11]=CONTROL;f[54:57,11:11+g.control*14]=CONTROL;f[58:60,8:8+g.choice*13]=CHOICE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q231(ARCBaseGame):
 def __init__(self):self.display=D(self);self.evidence=[];self.last=self.control=self.choice=0;self.direction=1;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q231",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.evidence=[];self.last=self.control=self.choice=0;self.direction=1;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.evidence.append((a,response(x["rule"],a,self.last,self.control,self.direction)));self.last=a
  elif a==4:
   old=self.control;self.control=(self.control+self.direction)%3
   if self.control in (0,2):self.direction=-self.direction
   self.evidence.append((4,self.control,self.direction));self.last=old
  elif a==5:self.choice=(self.choice+1)%4
  elif a==6:
   if tuple(self.evidence)==expected(x) and self.choice==x["rule"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
