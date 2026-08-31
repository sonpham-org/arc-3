"""q225 Vivarium Veil -- schedule attention while partner favor changes hidden fauna motion."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HABITAT,STRATUM,FAUNA,FOCUS,TEMP,FAVOR,GOAL,BAD=11,10,9,14,6,4,2,15,8
LEVELS=[{"name":"Warm Shelf","plan":(1,4)},{"name":"Hidden Fauna","plan":(2,1,4)},{"name":"Fair Help","plan":(3,5,4,1)},{"name":"Coupled Habitat","plan":(1,4,2,5,3)},{"name":"Remembered Favor","plan":(2,5,3,4,1,5)},{"name":"Vivarium Veil","plan":(3,4,1,5,2,4,3,5)}]
def advance(s,a):
 fauna,focus,temp,favor,helps=s;fauna=list(fauna)
 if a in (1,2,3):
  focus=a-1
  for i in range(3):
   if i!=focus:fauna[i]=(fauna[i]+temp+favor+i+1)%5
 elif a==4:
  temp=(temp+1)%4
  for i in range(3):
   if i!=focus:fauna[i]=(fauna[i]+temp+i)%5
 elif a==5:
  fair=fauna[focus]==min(fauna);favor=(favor+(1 if fair else 3))%4;helps+=1;fauna[focus]=(fauna[focus]+favor)%5
 return tuple(fauna),focus,temp,favor,helps
def target(x):
 s=((0,2,4),0,0,0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HABITAT
  for i,v in enumerate(g.fauna):y=9+i*14;f[y:y+11,8:56]=STRATUM;f[y+3:y+8,10+v*9:17+v*9]=FAUNA-i
  f[7+g.focus*14:10+g.focus*14,5:8]=FOCUS;f[51:54,8:11+g.temp*11]=TEMP;f[56:59,8:11+g.favor*11]=FAVOR;f[56:59,50:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q225(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q225",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.fauna=(0,2,4);self.focus=self.temp=self.favor=self.helps=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.fauna,self.focus,self.temp,self.favor,self.helps=advance((self.fauna,self.focus,self.temp,self.favor,self.helps),a)
  elif a==6:
   if (self.fauna,self.focus,self.temp,self.favor,self.helps)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
