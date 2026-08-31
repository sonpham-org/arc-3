"""q561 Aurora Counter -- shape a legible rival before exploiting its response."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OBSERVATORY,CURTAIN,MOTE,RIVAL,TREATMENT,HYSTERESIS,COUNTER,BAD=1,10,12,14,6,4,11,7,15
LEVELS=[{"name":"Three Treatments","plan":(1,2,3,5)},{"name":"Reordered Rival","plan":(2,3,1,5)},{"name":"Control Return","plan":(1,4,2,3,1,5)},{"name":"Shaped Counter","plan":(3,1,4,2,1,3,5)},{"name":"Hysteretic Rival","plan":(2,4,1,3,2,1,5)},{"name":"Aurora Counter","plan":(4,3,1,4,2,3,1,5)}]
def advance(s,a):
 recent,rival,control,hyst,shaped,counter=s;recent=list(recent)
 if a in (1,2,3):recent.append(a);rival=(sum(recent[-3:])+hyst+control)%3;hyst=(hyst+a+control)%5;shaped=len(recent)>=3 and set(recent[-3:])=={1,2,3}
 elif a==4:control=(control-1)%3;hyst=(hyst+2)%5
 elif a==5:
  if not shaped:return None
  counter=(tuple(recent[-3:]),rival,control,hyst)
 return tuple(recent),rival,control,hyst,shaped,counter
def target(x):
 s=((),0,0,0,False,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=OBSERVATORY;f[8:31,7:29]=RIVAL;f[8:31,35:57]=CURTAIN
  for i,a in enumerate(g.recent[-8:]):x=9+(i%4)*10;y=11+(i//4)*10;f[y:y+6,x:x+7]=MOTE-a
  f[37:40,8:11+g.rival*14]=TREATMENT;f[44:47,8:11+g.hyst*9]=HYSTERESIS;f[54:57,40:56]=COUNTER if g.counter else CURTAIN
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q561(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q561",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.rival=self.control=self.hyst=0;self.shaped=False;self.counter=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.recent,self.rival,self.control,self.hyst,self.shaped,self.counter),a)
   if s is None:self.bad=True;self.lose()
   else:self.recent,self.rival,self.control,self.hyst,self.shaped,self.counter=s
  elif a==6:
   if (self.recent,self.rival,self.control,self.hyst,self.shaped,self.counter)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
